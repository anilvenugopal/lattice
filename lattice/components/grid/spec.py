"""Declarative grid definition. One GridSpec per list screen.

A GridSpec says what rows exist (`query`), how they look (`columns`), how users
narrow them (`search`, `filters`, `views`) and what users can do with a selection
(`actions`). The grid package supplies everything else: paging, sorting,
selection, the action bar, confirm and input dialogs, the side panel, CSV export,
column visibility, keyboard control, URL state and Ctrl+J search entries.

Reference: docs/GRID.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import Select
from sqlalchemy.orm import Session

ColumnKind = Literal[
    "text", "strong", "mono", "number", "money", "percent", "date", "datetime", "ago",
    "badge", "bool", "tags", "progress", "user", "star", "template",
]
Tone = Literal["neutral", "info", "success", "warning", "danger", "accent"]
Options = list[tuple[str, str]] | Callable[[Session, Any], list[tuple[str, str]]]


@dataclass
class Column:
    key: str                       # label of a column in GridSpec.query
    label: str
    kind: ColumnKind = "text"
    sortable: bool = True
    hidden: bool = False           # off until the user turns it on in the Columns menu
    required: bool = False         # cannot be turned off
    width: str = ""                # CSS width, e.g. "120px"
    align: Literal["", "right", "center"] = ""
    tones: dict[str, Tone] = field(default_factory=dict)    # badge: value -> tone
    labels: dict[str, str] = field(default_factory=dict)    # value -> display text
    href: str = ""                 # link target, formatted with the row: "/work/{id}"
    secondary: str = ""            # key shown as a muted second line
    template: str = ""             # kind="template": partial rendered with `row`, `col`
    star_action: str = ""          # kind="star": action key toggled by clicking the star


@dataclass
class Filter:
    key: str                       # column label in GridSpec.query
    label: str
    options: Options
    multiple: bool = True


@dataclass
class View:
    """A named preset of filters shown as a tab above the grid (or in the sidebar)."""

    key: str
    label: str
    where: dict[str, Any] = field(default_factory=dict)   # "$me" means the current user id
    sort: str = ""


@dataclass
class Field:
    """An input collected in a dialog before an action runs."""

    name: str
    label: str
    kind: Literal["text", "textarea", "select", "number", "date"] = "text"
    options: Options = field(default_factory=list)
    required: bool = False
    default: str = ""
    placeholder: str = ""


@dataclass
class ActionContext:
    db: Session
    user: Any                       # CurrentUser
    ids: list[Any]                  # eligible ids, already scoped by GridSpec.query
    rows: list[dict]                # the eligible rows as the grid query returns them
    values: dict[str, str]          # Field inputs

    @property
    def count(self) -> int:
        return len(self.ids)


@dataclass
class ActionResult:
    message: str = ""
    tone: Tone = "success"
    refresh: bool = True
    clear_selection: bool = True
    redirect: str = ""


ActionHandler = Callable[[ActionContext], ActionResult | str | None]


@dataclass
class Action:
    """A button in the grid's action bar and row menu.

    scope: "none" needs no selection (e.g. New), "single" exactly one row,
    "multi" one or more rows.
    Either `handler` runs server-side, or `href` navigates ("/work/{id}" for single).
    `when` restricts eligible rows, e.g. {"status": ["failed"]}: the button is
    disabled unless at least one selected row matches, and the server drops rows
    that do not match before calling the handler (the toast reports them as
    skipped). `when` keys must hold plain JSON values (str, int, bool, None).
    The handler must not commit; the grid commits after writing the audit event.
    """

    key: str
    label: str
    scope: Literal["none", "single", "multi"] = "multi"
    handler: ActionHandler | None = None
    href: str = ""
    confirm: str = ""               # "{count}" is replaced with the selection size
    tone: Literal["default", "primary", "danger"] = "default"
    icon: str = ""
    roles: tuple[str, ...] = ()
    fields: list[Field] = field(default_factory=list)
    when: dict[str, list[Any]] = field(default_factory=dict)
    in_row_menu: bool = True

    def applies(self, row: dict) -> bool:
        """True when the row satisfies `when` (always true without `when`)."""
        return all(row.get(k) in allowed for k, allowed in self.when.items())


@dataclass
class Palette:
    """Makes rows findable from Ctrl+J (one search provider per grid, see lattice/components/search/providers.py).

    Strings are formatted with the row; `href` values are URL-encoded.
    """

    title: str
    href: str
    subtitle: str = ""
    icon: str = "link"


@dataclass
class GridSpec:
    key: str
    title: str
    path: str                                          # page that hosts the grid
    query: Callable[[Session, Any], Select]            # labeled columns, must include "id"
    columns: list[Column]
    search: list[str] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    views: list[View] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    selection: Literal["multi", "single", "none"] = "multi"
    default_sort: str = "-id"                          # "-" prefix sorts descending
    row_href: str = ""                                 # Enter / double-click target
    panel: Callable[[Session, Any, dict], dict] | None = None
    panel_title: str = "{id}"
    layout: Literal["table", "split"] = "table"        # split: list + reading pane
    row_class: Callable[[dict], str] | None = None
    poll_seconds: int = 0
    export: bool = True
    roles: tuple[str, ...] = ()
    search_placeholder: str = "Search"
    empty_title: str = "Nothing here yet"
    empty_text: str = ""
    palette: Palette | None = None

    def column(self, key: str) -> Column | None:
        return next((c for c in self.columns if c.key == key), None)

    def action(self, key: str) -> Action | None:
        return next((a for a in self.actions if a.key == key), None)

    def actions_for(self, user) -> list[Action]:
        """Actions the user's roles allow. The server checks this; hiding a button is not enough."""
        return [a for a in self.actions if user.has_any(a.roles)]

    @staticmethod
    def when_keys(actions: list[Action]) -> list[str]:
        """Row keys the client needs to evaluate `when` for these actions."""
        return sorted({k for a in actions for k in a.when})

    def view(self, key: str) -> View | None:
        return next((v for v in self.views if v.key == key), None)
