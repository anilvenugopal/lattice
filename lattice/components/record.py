"""The record page: the standard detail page for one row of a grid.

A RecordPage is declared on a GridSpec and reuses it: the row is read through
the grid's query (so a record page shows nothing its list would not), the
properties render with the grid's Column kinds, the header badge uses the
status Column's labels and tones, and the header's buttons are the grid's
actions that apply to this row, run through the grid's action endpoint.

Guide: lattice/help/developer/building-apps/record-pages.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import HTTPException, Request

from lattice.components.grid import engine
from lattice.components.grid.render import field_config
from lattice.components.grid.spec import GridSpec
from lattice.components.references import Ref, urn
from lattice.kernel.database import Db
from lattice.kernel.services import audit, notifications
from lattice.kernel.web import fmt, fmt_url, render_page


@dataclass
class Panel:
    """A section of the record page, drawn by the app's own template."""

    key: str                        # unique on the page
    label: str                      # card heading, formatted with the row: "Tickets for {account}"
    template: str                   # "{app}/…html", rendered with `record`, `page` and `load`'s values
    # (request, db, row) -> extra template values, e.g. an embedded grid; None: none
    load: Callable[[Request, Db, dict], dict] | None = None
    place: Literal["main", "side", "full"] = "main"  # left column, right column, or full width below
    permission: str = ""            # who sees it; empty = everyone who can open the record
    flush: bool = False             # no padding in the card body, e.g. for a grid


@dataclass
class RecordPanel:
    """A panel an app adds to other apps' record pages, matched on reference kind (ADR 0011).

    It works from the record's reference, not the other app's row: its template receives
    `subject` (a Ref, with .urn, .kind and .id) and `values` from `load`.
    """

    key: str                        # "{app}.{name}", unique in the host
    label: str                      # card heading
    template: str                   # "{app}/…html"
    kinds: list[str] | str = "*"    # reference kinds it applies to, or "*" for every kind
    # (request, db, subject) -> template values; None: none
    load: Callable[[Request, Db, Ref], dict] | None = None
    place: Literal["main", "side", "full"] = "side"
    permission: str = ""
    flush: bool = False

    def applies(self, kind: str) -> bool:
        return self.kinds == "*" or kind in self.kinds


PANELS: list[RecordPanel] = []


@dataclass
class Link:
    """A header button that opens a page, e.g. the record's edit form."""

    label: str
    href: str                       # formatted with the row: "/showcase/claims/{id}/assessment"
    icon: str = ""
    tone: Literal["default", "primary", "danger", "ghost"] = "default"
    permission: str = ""


@dataclass
class RecordPage:
    """One record of a grid as a full page: header, properties, panels and history."""

    grid: GridSpec                  # its query loads the row; its columns and actions are reused
    nav_key: str                    # the page's NavNode (hidden, parent: the list's node)
    title: str                      # formatted with the row: "{ref} · {title}"
    subtitle: str = ""              # formatted with the row
    status: str = ""                # a column shown as a badge beside the title
    properties: list[str] = field(default_factory=list)  # column keys for the Details card
    details_title: str = "Details"
    panels: list[Panel] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)       # header buttons before the actions
    actions: bool = True            # the grid's row actions that apply to this row
    history: bool = True            # the audit timeline of the grid's actions on this row
    back: str = ""                  # "Back to list" target; default: the grid's path
    crumb: str = ""                 # breadcrumb text, formatted with the row; default: title
    # The record's reference kind ("showcase.claim"): other apps' RecordPanels for it appear
    # after the app's own panels. Empty: none.
    reference_kind: str = ""

    def __post_init__(self):
        unknown = [k for k in self.properties + ([self.status] if self.status else [])
                   if not self.grid.column(k)]
        if unknown:
            raise ValueError(f"Record page for {self.grid.key!r}: no grid column "
                             f"{', '.join(map(repr, unknown))}")


def load_row(request: Request, db: Db, page: RecordPage, record_id: Any) -> dict:
    """The row through the grid's query and the grid's permission; 404 when the user can't see it."""
    user = request.state.user
    if not user.can(page.grid.permission):
        raise HTTPException(403)
    rows = engine.fetch_by_ids(page.grid, db, user, [record_id])
    if not rows:
        raise HTTPException(404, detail="That record does not exist, or you cannot see it.")
    return rows[0]


def render_record_page(request: Request, db: Db, page: RecordPage, record_id: Any, **extra):
    """The record page for one row. Extra keyword arguments reach the panel templates."""
    user = request.state.user
    row = load_row(request, db, page, record_id)
    grid = page.grid
    actions = [a for a in grid.actions_for(user)
               if a.scope != "none" and a.applies(row) and (a.handler or a.href != grid.row_href)]
    panels = []
    for panel in page.panels:
        if user.can(panel.permission):
            values = panel.load(request, db, row) if panel.load else {}
            panels.append({"panel": panel, "label": fmt(panel.label, row), "values": values})
    if page.reference_kind:
        subject = Ref(page.reference_kind, str(row["id"]))
        for panel in PANELS:
            if panel.applies(subject.kind) and user.can(panel.permission):
                values = panel.load(request, db, subject) if panel.load else {}
                panels.append({"panel": panel, "label": panel.label, "values": values,
                               "subject": subject})
    title = fmt(page.title, row)
    subject = urn(page.reference_kind, row["id"]) if page.reference_kind else ""
    follow = {"subject": subject, "following": notifications.following(db, user.id, subject)} \
        if subject else None
    return render_page(
        request, "components/record_page.html", page.nav_key,
        page=page, record=row, spec=grid, title=title, subtitle=fmt(page.subtitle, row),
        links=[(link, fmt_url(link.href, row)) for link in page.links if user.can(link.permission)],
        actions=actions if page.actions else [],
        panels=panels,
        events=audit.history(db, grid.key, row["id"]) if page.history else None,
        config={"endpoint": f"/_grid/{grid.key}", "id": str(row["id"]), "back": page.back or grid.path,
                "actions": {a.key: _action_config(a, db, user) for a in actions}},
        follow=follow, crumb=fmt(page.crumb, row) if page.crumb else title, **extra)


def _action_config(action, db, user) -> dict:
    return {"key": action.key, "label": action.label, "scope": action.scope, "confirm": action.confirm,
            "href": action.href, "tone": action.tone,
            "fields": [field_config(f, db, user) for f in action.fields]}
