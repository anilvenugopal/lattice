"""Declarative grid definition. One GridSpec per list screen.

A GridSpec says what rows exist (`query`), how they look (`columns`), how users
narrow them (`search`, `filters`, `views`) and what users can do with a selection
(`actions`). The grid package supplies everything else: paging, sorting,
selection, the action bar, confirm and input dialogs, the side panel, CSV export,
column visibility, keyboard control, URL state and Ctrl+J search entries.

Guide: lattice/help/developer/building-apps/grids.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from lattice.kernel.database import Db
from lattice.kernel.sql import Query

ColumnKind = Literal[
    "text", "strong", "mono", "number", "money", "percent", "date", "datetime", "ago",
    "badge", "bool", "tags", "progress", "user", "star", "template",
]
Tone = Literal["neutral", "info", "success", "warning", "danger", "accent"]
Options = list[tuple[str, str]] | Callable[[Db, Any], list[tuple[str, str]]]


@dataclass
class Column:
    """A column of the grid. Its `labels` and `tones` are the one place a status value's text and
    colour are declared.
    """

    key: str                       # label of a column in GridSpec.query
    label: str                     # header text
    kind: ColumnKind = "text"      # how values render, see Column kinds
    sortable: bool = True          # header click sorts by it
    hidden: bool = False           # off until the user turns it on in the Columns menu
    required: bool = False         # cannot be turned off
    width: str = ""                # CSS width, e.g. "120px"
    align: Literal["", "right", "center"] = ""  # header and cell alignment
    tones: dict[str, Tone] = field(default_factory=dict)    # badge: value -> tone
    labels: dict[str, str] = field(default_factory=dict)    # value -> display text
    href: str = ""                 # link target, formatted with the row: "/work/{id}"
    secondary: str = ""            # key shown as a muted second line
    template: str = ""             # kind="template": partial rendered with `row`, `col`
    star_action: str = ""          # kind="star": action key toggled by clicking the star


@dataclass
class Filter:
    """A dropdown in the filter bar that narrows rows to the chosen values of one column."""

    key: str                       # column label in GridSpec.query
    label: str                      # dropdown text
    options: Options                # (value, label) pairs, or a function (db, user) returning them
    multiple: bool = True           # allow several values (matched with IN)


@dataclass
class View:
    """A named preset of filters shown as a tab above the grid (or in the sidebar)."""

    key: str                        # in the URL as ?view=
    label: str                      # tab text
    where: dict[str, Any] = field(default_factory=dict)   # "$me" means the current user id
    sort: str = ""                  # sort applied with the view, e.g. "-created_at"


@dataclass
class Field:
    """An input collected in a dialog before an action runs."""

    name: str                       # key in ActionContext.values
    label: str                      # input label
    kind: Literal["text", "textarea", "select", "number", "date"] = "text"  # input type
    # kind="select": (value, label) pairs or a function (db, user)
    options: Options = field(default_factory=list)
    required: bool = False          # the dialog will not submit without it
    default: str = ""               # initial value
    placeholder: str = ""           # hint inside the empty input


@dataclass
class ActionContext:
    """What an action handler receives."""

    db: Db                          # the request's Db, in the request's transaction
    user: Any                       # CurrentUser
    ids: list[Any]                  # eligible ids, already scoped by GridSpec.query
    rows: list[dict]                # the eligible rows as the grid query returns them
    values: dict[str, str]          # Field inputs

    @property
    def count(self) -> int:
        return len(self.ids)


@dataclass
class ActionResult:
    """What an action handler may return. A plain string is the success message."""

    message: str = ""               # toast text; default "{action label}: {n} updated."
    tone: Tone = "success"          # toast tone
    refresh: bool = True            # reload the grid rows
    clear_selection: bool = True    # empty the selection after
    redirect: str = ""              # navigate to this URL instead of refreshing


ActionHandler = Callable[[ActionContext], ActionResult | str | None]


@dataclass
class Action:
    """A button in the grid's action bar and row menu.

    # selection it needs, see above
    scope: "none" needs no selection (e.g. New), "single" exactly one row,
    "multi" one or more rows.
    Either `handler` runs server-side, or `href` navigates ("/work/{id}" for single).
    `when` restricts eligible rows, e.g. {"status": ["failed"]}: the button is
    disabled unless at least one selected row matches, and the server drops rows
    that do not match before calling the handler (the toast reports them as
    skipped). `when` keys must hold plain JSON values (str, int, bool, None).
    The handler runs in the request's transaction, with the grid's audit events; if it
    raises, nothing is saved.
    """

    key: str  # unique in the grid; the audit event is "{grid key}.{action key}"
    label: str                      # button text
    scope: Literal["none", "single", "multi"] = "multi"  # selection it needs, see above
    handler: ActionHandler | None = None  # runs server-side with an ActionContext
    href: str = ""                  # navigate instead of running a handler
    confirm: str = ""               # "{count}" is replaced with the selection size
    tone: Literal["default", "primary", "danger"] = "default"  # button style
    icon: str = ""                  # icon name, see Slots and icons
    permission: str = ""            # who may run it; empty = every user who can see the grid
    # inputs asked for in a dialog before the action runs
    fields: list[Field] = field(default_factory=list)
    # row values the action applies to, e.g. {"status": ["failed"]}
    when: dict[str, list[Any]] = field(default_factory=dict)
    in_row_menu: bool = True        # also list the action in each row's ⋯ menu

    def applies(self, row: dict) -> bool:
        """True when the row satisfies `when` (always true without `when`)."""
        return all(row.get(k) in allowed for k, allowed in self.when.items())


@dataclass
class Palette:
    """Makes rows findable from Ctrl+J (one search provider per grid, see lattice/components/search/providers.py).

    Strings are formatted with the row; `href` values are URL-encoded.
    """

    title: str                      # result title, formatted with the row: "{ref} · {title}"
    href: str                       # opened with Enter: "/demo/work/{id}"
    subtitle: str = ""              # muted second line
    icon: str = "link"              # result icon


@dataclass
class GridSpec:
    """One list screen: what rows exist, how they look, how users narrow them and what they can do
    with a selection.
    """

    key: str                        # unique: "{app}.{name}"
    title: str                      # heading and Ctrl+J source name
    path: str                                          # page that hosts the grid
    # A named query (sql/<area>.sql) returning the rows, with an "id" column.
    # It may use :user_id (the signed-in user) to scope rows.
    query: Query
    columns: list[Column]           # in display order
    search: list[str] = field(default_factory=list)  # columns matched by the search box (ILIKE)
    filters: list[Filter] = field(default_factory=list)  # dropdowns in the filter bar
    views: list[View] = field(default_factory=list)  # tabs of preset filters
    actions: list[Action] = field(default_factory=list)  # buttons in the action bar and row menu
    selection: Literal["multi", "single", "none"] = "multi"  # how many rows can be selected
    default_sort: str = "-id"                          # "-" prefix sorts descending
    row_href: str = ""                                 # Enter / double-click target
    # (db, user, row) -> context for the side panel; None: no panel
    panel: Callable[[Db, Any, dict], dict] | None = None
    panel_title: str = "{id}"       # side panel heading, formatted with the row
    layout: Literal["table", "split"] = "table"        # split: list + reading pane
    row_class: Callable[[dict], str] | None = None  # extra CSS class per row, e.g. unread
    poll_seconds: int = 0           # reload rows every n seconds; 0 = never
    export: bool = True             # offer CSV download of the filtered rows
    permission: str = ""            # who may open the grid; empty = every signed-in user
    search_placeholder: str = "Search"  # search box hint
    empty_title: str = "Nothing here yet"  # shown when no rows match
    empty_text: str = ""            # second line under empty_title
    palette: Palette | None = None  # make rows findable from Ctrl+J

    @property
    def app_key(self) -> str:
        """The owning app's key: the grid key's prefix ("demo.jobs" -> "demo"); "" for platform grids."""
        return self.key.partition(".")[0] if "." in self.key else ""

    def column(self, key: str) -> Column | None:
        return next((c for c in self.columns if c.key == key), None)

    def action(self, key: str) -> Action | None:
        return next((a for a in self.actions if a.key == key), None)

    def actions_for(self, user) -> list[Action]:
        """Actions the user's roles allow. The server checks this; hiding a button is not enough."""
        return [a for a in self.actions if user.can(a.permission)]

    @staticmethod
    def when_keys(actions: list[Action]) -> list[str]:
        """Row keys the client needs to evaluate `when` for these actions."""
        return sorted({k for a in actions for k in a.when})

    def view(self, key: str) -> View | None:
        return next((v for v in self.views if v.key == key), None)
