"""Builds the template context for a grid and renders grid pages."""

from __future__ import annotations

import contextlib
import json
from datetime import date

from fastapi import HTTPException, Request
from starlette.datastructures import QueryParams

from lattice.components.grid import engine
from lattice.components.grid.spec import Field, Filter, GridSpec
from lattice.kernel.database import Db
from lattice.kernel.services import preferences
from lattice.kernel.web import fmt, label_for, render, render_page


def hidden_columns(spec: GridSpec, user) -> set[str]:
    saved = user.prefs.get(f"grid.{spec.key}.hidden")
    hidden = set(saved) if saved is not None else {c.key for c in spec.columns if c.hidden}
    return {k for k in hidden if not (spec.column(k) and spec.column(k).required)}


def resolve_options(options, db: Db, user) -> list[tuple[str, str]]:
    return options(db, user) if callable(options) else options


def field_config(fld: Field, db, user) -> dict:
    return {"name": fld.name, "label": fld.label, "kind": fld.kind, "required": fld.required,
            "default": fld.default, "placeholder": fld.placeholder,
            "options": [list(o) for o in resolve_options(fld.options, db, user)]}


def narrow_label(spec: GridSpec, key: str, value: str) -> str:
    """Chip text for a narrowing: "Construction: Frame", "Reported: 9 Oct 2026"."""
    col = spec.column(key)
    text = str(label_for(col, value))
    with contextlib.suppress(ValueError):
        text = date.fromisoformat(value).strftime("%-d %b %Y") if len(value) == 10 else text
    return f"{col.label if col else key.replace('_', ' ').capitalize()}: {text}"


def build_grid(request: Request, db: Db, spec: GridSpec, *, views_in_nav: bool = False,
               sync_url: bool = True, fixed: dict | None = None) -> dict:
    """Template context for components/grid.html: render it with `data_grid(grid)`.

    sync_url=True: the grid owns the page URL. It starts from the URL's state and writes
    its state back to it. sync_url=False (a grid embedded in another page): it starts from
    its defaults and leaves the URL alone.
    fixed: column -> value (or list of values) the rows are narrowed to on every request,
    e.g. {"customer_id": 42} for one customer's tickets. Users cannot change it. It
    narrows what the grid shows; it is not access control (the query is).
    """
    user = request.state.user
    default_size = int(preferences.get(user, "page_size"))
    params = request.query_params if sync_url else QueryParams()
    gq = engine.GridQuery.from_params(params, spec, default_size)
    # x_ values in the URL (a chart clicked on another page) narrow the rows too, shown as
    # chips the user can remove; the page's own fixed values are not shown.
    pinned = {k: [str(x) for x in (v if isinstance(v, (list, tuple)) else [v])]
              for k, v in (fixed or {}).items()}
    narrowed = {k: v for k, v in gq.fixed.items() if k not in pinned}
    gq.fixed = {**narrowed, **pinned}
    page = engine.fetch_page(spec, db, user, gq)
    hidden = hidden_columns(spec, user)
    actions = spec.actions_for(user)
    filters: list[tuple[Filter, list, list]] = [
        (f, resolve_options(f.options, db, user), gq.filters.get(f.key, []))
        for f in spec.filters if f.key not in gq.fixed
    ]
    current_sort = gq.effective_sort(spec)
    config = {
        "key": spec.key,
        "path": request.url.path,           # the page the grid is on, for its URL state
        "pinned": [f"x_{k}" for k in pinned],
        "endpoint": f"/_grid/{spec.key}",
        "selection": spec.selection,
        "layout": spec.layout,
        "hasPanel": spec.panel is not None or spec.layout == "split" or not spec.row_href,
        "rowHref": spec.row_href,
        "poll": spec.poll_seconds,
        "syncUrl": sync_url,
        "spatial": spec.spatial is not None,
        "viewsInNav": views_in_nav,
        "total": page.total,
        "narrowed": [{"name": f"x_{k}", "value": v, "label": narrow_label(spec, k, v)}
                     for k, values in narrowed.items() for v in values],
        "view": gq.view,
        "defaultView": spec.views[0].key if spec.views else "",
        "sort": current_sort,
        "defaultSize": default_size,
        "hidden": sorted(hidden),
        "actions": {a.key: {
            "key": a.key, "label": a.label, "scope": a.scope, "href": a.href,
            "confirm": a.confirm, "tone": a.tone, "when": a.when,
            "fields": [field_config(f, db, user) for f in a.fields],
        } for a in actions},
    }
    return {
        "spec": spec,
        "gq": gq,
        "page": page,
        "columns": [c for c in spec.columns if c.key not in hidden],
        "all_columns": spec.columns,
        "hidden": hidden,
        "filters": filters,
        "toolbar_actions": [a for a in actions if a.scope == "none"],
        "selection_actions": [a for a in actions if a.scope != "none"],
        "row_actions": [a for a in actions if a.scope != "none" and a.in_row_menu],
        "when_keys": spec.when_keys(actions),
        "sort": current_sort,
        "views_in_nav": views_in_nav,
        "config": config,
        "page_sizes": engine.PAGE_SIZES,
    }


def render_grid_page(request: Request, db: Db, spec: GridSpec, nav_key: str, *,
                     title: str = "", subtitle: str = "", views_in_nav: bool = False):
    """A full page holding one grid: the standard list screen."""
    grid = build_grid(request, db, spec, views_in_nav=views_in_nav)
    return render_page(request, "components/grid_page.html", nav_key, grid=grid,
                       title=title or spec.title, subtitle=subtitle)


def render_panel(request: Request, db: Db, spec: GridSpec, row_id, *, preview: bool = False):
    """The side panel / reading pane for one row (components/grid_panel.html).

    preview=True is the read-only form the Ctrl+J preview pane shows: no actions, no close
    button, and an Open button when the grid has a row_href.
    """
    user = request.state.user
    found = engine.fetch_by_ids(spec, db, user, [row_id])
    if not found:
        raise HTTPException(404, detail="That row no longer exists.")
    row = found[0]
    extra = spec.panel(db, user, row) if spec.panel else {}
    # The panel header already links to row_href, so an action that only opens it is left out.
    actions = [] if preview else [
        a for a in spec.actions_for(user)
        if a.scope != "none" and a.href != spec.row_href and a.applies(row)]
    # A panel that changes the row (e.g. marks a message read) asks the grid to refresh.
    refresh = extra.pop("refresh_grid", False) and not preview
    headers = {"HX-Trigger": json.dumps({"gridrefresh": {"key": spec.key}})} if refresh else None
    return render(request, "components/grid_panel.html", headers=headers,
                  spec=spec, row=row, title=fmt(spec.panel_title, row), preview=preview,
                  body_template=extra.pop("template", ""), actions=actions, **extra)
