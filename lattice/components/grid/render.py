"""Builds the template context for a grid and renders grid pages."""

from __future__ import annotations

import json

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from lattice.components.grid import engine
from lattice.components.grid.spec import Field, Filter, GridSpec
from lattice.kernel.services import preferences
from lattice.kernel.web import fmt, render, render_page


def hidden_columns(spec: GridSpec, user) -> set[str]:
    saved = user.prefs.get(f"grid.{spec.key}.hidden")
    hidden = set(saved) if saved is not None else {c.key for c in spec.columns if c.hidden}
    return {k for k in hidden if not (spec.column(k) and spec.column(k).required)}


def resolve_options(options, db: Session, user) -> list[tuple[str, str]]:
    return options(db, user) if callable(options) else options


def _field_config(fld: Field, db, user) -> dict:
    return {"name": fld.name, "label": fld.label, "kind": fld.kind, "required": fld.required,
            "default": fld.default, "placeholder": fld.placeholder,
            "options": [list(o) for o in resolve_options(fld.options, db, user)]}


def build_grid(request: Request, db: Session, spec: GridSpec, *, views_in_nav: bool = False,
               sync_url: bool = True) -> dict:
    """Template context for components/grid.html. Reads grid state from the request URL."""
    user = request.state.user
    default_size = int(preferences.get(user, "page_size"))
    gq = engine.GridQuery.from_params(request.query_params, spec, default_size)
    page = engine.fetch_page(spec, db, user, gq)
    hidden = hidden_columns(spec, user)
    actions = spec.actions_for(user)
    filters: list[tuple[Filter, list, list]] = [
        (f, resolve_options(f.options, db, user), gq.filters.get(f.key, []))
        for f in spec.filters
    ]
    current_sort = gq.effective_sort(spec)
    config = {
        "key": spec.key,
        "path": spec.path,
        "endpoint": f"/_grid/{spec.key}",
        "selection": spec.selection,
        "layout": spec.layout,
        "hasPanel": spec.panel is not None or spec.layout == "split" or not spec.row_href,
        "rowHref": spec.row_href,
        "poll": spec.poll_seconds,
        "syncUrl": sync_url,
        "viewsInNav": views_in_nav,
        "total": page.total,
        "view": gq.view,
        "defaultView": spec.views[0].key if spec.views else "",
        "sort": current_sort,
        "defaultSize": default_size,
        "hidden": sorted(hidden),
        "actions": {a.key: {
            "key": a.key, "label": a.label, "scope": a.scope, "href": a.href,
            "confirm": a.confirm, "tone": a.tone, "when": a.when,
            "fields": [_field_config(f, db, user) for f in a.fields],
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


def render_grid_page(request: Request, db: Session, spec: GridSpec, nav_key: str, *,
                     title: str = "", subtitle: str = "", views_in_nav: bool = False):
    """A full page holding one grid: the standard list screen."""
    grid = build_grid(request, db, spec, views_in_nav=views_in_nav)
    return render_page(request, "components/grid_page.html", nav_key, grid=grid,
                       title=title or spec.title, subtitle=subtitle)


def render_panel(request: Request, db: Session, spec: GridSpec, row_id, *, preview: bool = False):
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
