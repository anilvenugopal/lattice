---
title: Grids
summary: The standard grid in depth. Declare a GridSpec and get search, filters, views, selection, actions, panels, export and Ctrl+J.
order: 20
keywords: gridspec grid table list column filter view action panel split export selection bulk palette embed
---

One component lists every kind of record in Lattice: work queues, job runs,
mailboxes, users, sessions, audit events. A screen declares a `GridSpec` in
Python and the grid supplies the behaviour.

The model is Foundry Workshop's object table:

- an object set (the **query**) feeds a table;
- the **selection** feeds actions and a detail view.

Every field of every class is listed in [Reference › Grid](../reference/grid.md).

> [!IMPORTANT]
> Every list of records is a `GridSpec`. Do not write a `<table>` for records,
> a pager, a filter bar, selection script or side panel of your own. If the grid
> cannot do something, extend `lattice/components/grid/` for everyone. A plain
> `.table` is only for short fixed lists inside a card (about ten rows, no
> selection), such as a user's sessions.

## What every grid gets

| Capability | How the user reaches it |
|---|---|
| Search across the `search` columns (every word must match) | The search box; `/` focuses it |
| Filters with multi- or single-select options | Filter chips in the toolbar |
| Views: named filter presets | Tabs above the toolbar, or sidebar links (`views_in_nav=True`) |
| Sort by any sortable column | Click the header; click again to reverse |
| Paging; the page size defaults to the user's preference | The footer |
| Single, multi, range and page selection; "select all N matching" | Click, Ctrl/⌘-click, Shift-click, the header checkbox, Ctrl+A, Space or X |
| An action bar, enabled by selection size and row state | Appears when rows are selected |
| A row menu with the same actions | `⋯` at the end of the row |
| Confirm and input dialogs | `Action.confirm`, `Action.fields` |
| A side panel (table layout) or reading pane (split layout) | Click a row; ↑/↓ follows; Esc closes |
| Open the full record | Double-click or Enter (`row_href`) |
| Show and hide columns, saved per user | The Columns menu |
| CSV export of the filtered rows (up to 50,000) | The download button |
| Live refresh | `poll_seconds` |
| State in the URL | Copy the address to share a filtered view |
| A Ctrl+J source with a preview | `palette=Palette(…)` |
| A home page count tile | `HomeTile(…)` in the manifest's `tiles` |
| One audit event per row per action | Automatic |

## Declaring a grid

```python
# apps/helpdesk/lattice_helpdesk/tickets.py — an app with key "helpdesk"
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from lattice.api import (EDITORS, Action, Column, Filter, GridSpec, Palette, User, View,
                         csrf_protect, get_db, render_grid_page)
from lattice_helpdesk.models import Ticket

STATUSES = [("new", "New"), ("open", "Open"), ("closed", "Closed")]
STATUS_TONES = {"new": "info", "open": "warning", "closed": "success"}


def query(db: Session, user):
    # Labeled columns. Must include "id". This is the access boundary.
    return (select(Ticket.id, Ticket.ref, Ticket.subject, Ticket.status, Ticket.assignee_id,
                   User.display_name.label("assignee"), Ticket.opened_at)
            .outerjoin(User, User.id == Ticket.assignee_id))


def close(ctx):
    ctx.db.execute(update(Ticket).where(Ticket.id.in_(ctx.ids)).values(status="closed"))
    return f"Closed {ctx.count} ticket(s)."     # a str or an ActionResult; do not commit


GRID = GridSpec(
    key="helpdesk.tickets", title="Tickets", path="/helpdesk/tickets", query=query,
    columns=[
        Column("ref", "Ref", kind="mono", required=True),
        Column("subject", "Subject", kind="strong"),
        Column("status", "Status", kind="badge", tones=STATUS_TONES, labels=dict(STATUSES)),
        Column("assignee", "Assignee", kind="user"),
        Column("opened_at", "Opened", kind="ago"),
    ],
    search=["ref", "subject", "assignee"],
    filters=[Filter("status", "Status", STATUSES)],
    views=[View("open", "Open", where={"status": ["new", "open"]}),
           View("mine", "Mine", where={"assignee_id": "$me"}),
           View("all", "All")],
    actions=[
        Action("new", "New ticket", scope="none", href="/helpdesk/tickets/new",
               tone="primary", icon="plus", roles=EDITORS),
        Action("close", "Close", handler=close, when={"status": ["new", "open"]},
               confirm="Close {count} ticket(s)?", roles=EDITORS),
    ],
    default_sort="-opened_at",
    row_href="/helpdesk/tickets/{id}",
    palette=Palette(title="{ref} · {subject}", href="/helpdesk/tickets/{id}"),
)

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/tickets")                  # mounted under /helpdesk by the host
def tickets(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, GRID, "tickets")
```

In the manifest: `grids=[GRID]`, `routers=[router]` and a `NavNode` for
`tickets`.

`create_app` refuses to start unless the grid key starts with the app key and a
dot (`helpdesk.`), and the path starts with the app's prefix (`/helpdesk`).

## The query

The query is a function `(db, user) -> Select`. Each selected column's label
is a row key: `Column`, `search`, `Filter`, `View`, `when`, `Palette` and URL
templates such as `{id}` all refer to these keys.

- **It must select `id`.** Selection, actions, panels and links use it.
- **Filter and view keys must be selected.** `View("mine", where={"assignee_id": "$me"})`
  needs `assignee_id` in the select. It does not need a `Column`; only keys in
  `columns` are shown.
- **It is the access boundary.** Filter out rows the user may not see here,
  for example `.where(Message.owner_id == user.id)` in the demo Inbox. Paging,
  panels, actions, export, tiles and Ctrl+J all run through it, so a row the
  query does not return cannot be reached any other way.

`$me` in a view's `where` is replaced with the signed-in user's id.

## Columns

Choose how a value renders with `kind`:

| Kind | Renders |
|---|---|
| `text` | Plain text |
| `strong` | Emphasised text, for the main column |
| `mono` | Monospace, for references and codes |
| `number`, `money`, `percent` | Formatted numbers |
| `date`, `datetime` | Absolute dates |
| `ago` | Relative or absolute time, by the user's preference |
| `badge` | A badge with `labels` and `tones` |
| `bool` | A tick or a dash |
| `tags` | Comma-separated values as tags |
| `progress` | A 0–100 bar |
| `user` | Avatar initials and a name |
| `star` | A toggle that runs the action named in `star_action` |
| `template` | Your own partial, which receives `row` and `col` |

Other column options:

| Option | Does |
|---|---|
| `secondary` | A muted second line from another key |
| `href` | Makes the value a link, filled from the row |
| `hidden` | Off until the user turns it on |
| `required` | Cannot be turned off |
| `width`, `align` | Layout |
| `sortable` | Defaults to true |

**Labels and tones are declared once, on the column.** Detail pages and panels
read them from there with `badge_for(spec.column("status"), value)`,
`label_for(…)` and `tone_for(…)`. Never pass a tone map to a template.

## Actions

| Field | Meaning |
|---|---|
| `scope` | `none`: a toolbar button that needs no selection. `single`: exactly one row. `multi`: one or more rows |
| `handler` | Runs on the server with an `ActionContext` (`db`, `user`, `ids`, `rows`, `values`, `count`). Returns a `str` message or an `ActionResult(message, tone, refresh, clear_selection, redirect)` |
| `href` | Navigate instead of running a handler; `{id}` is the selected row |
| `when` | Which rows it applies to, for example `{"status": ["failed"]}`. The button is enabled when at least one selected row qualifies; the server skips the others and the toast says how many |
| `fields` | Inputs asked for in a dialog: `Field(name, label, kind, options, required, default, placeholder)`, where `kind` is `text`, `textarea`, `select`, `number` or `date` |
| `confirm` | Confirmation text; `{count}` is replaced with the number of rows |
| `roles` | Who sees and may run it; the server checks again |
| `tone`, `icon`, `in_row_menu` | Presentation |

When an action runs, the server:

1. checks the user holds one of `roles`;
2. reloads the selected rows through the query (up to 10,000 for "select all");
3. drops the rows that fail `when`;
4. calls the handler;
5. writes one audit event per row (`{grid key}.{action key}`) and commits.

**The handler must not commit.** If it raises, nothing is written.

Options for a `select` field or a filter can be a list of `(value, label)`
pairs or a function `(db, user)` that returns one, such as `users.options` for
a list of people.

## Layouts and panels

**Table** (`layout="table"`, the default):

- Clicking a row opens the side panel when the grid has a `panel`, or when it
  has no `row_href`.
- Otherwise a click selects the row, and Enter or a double-click opens
  `row_href`.

**Split** (`layout="split"`) shows the list on the left and a reading pane on
the right, as in the demo Inbox.

A **panel** is a function `(db, user, row) -> dict`. It returns a
`template` and the context for it:

```python
def panel(db, user, row):
    return {"template": "helpdesk/ticket_panel.html",
            "ticket": db.get(Ticket, row["id"]),
            "events": audit.history(db, "helpdesk.tickets", row["id"], limit=5)}
```

- Without `panel`, the grid shows every column as a property list.
- `panel_title` sets the heading, filled from the row.
- The panel shows the actions that apply to the row.
- Return `"refresh_grid": True` when opening the panel changed the row, such
  as marking a message read.

Ctrl+J shows the same panel as its preview, read-only: no actions, no close
button, and an Open button when the grid has a `row_href`.

## Selection

- Search, filter and view changes clear the selection. Paging and sorting keep it.
- "Select all N matching" sends the filter state, not ids. The server runs the
  query again (up to 10,000 rows), so the action applies to exactly what the
  user sees.
- `selection="single"` or `"none"` limits it.

## Shared endpoints

Every grid uses the same endpoints, so apps never write list endpoints:

| Endpoint | Does |
|---|---|
| `GET /_grid/{key}/rows` | Rows for the current search, filters, view, sort and page |
| `GET /_grid/{key}/panel/{id}` | The side panel for one row |
| `POST /_grid/{key}/action/{action}` | Runs an action (JSON: `ids` or the filter state, and `values`) |
| `POST /_grid/{key}/columns` | Saves the user's hidden columns |
| `GET /_grid/{key}/export.csv` | CSV of the filtered rows |

## Embedding a grid in another page

`render_grid_page` makes a page that is only the grid. To put a grid inside
another page, such as a list of related records on a detail page, build its
context and place it with the `data_grid` macro:

```python
grid = build_grid(request, db, GRID, sync_url=False)
return render_page(request, "helpdesk/customer.html", "customers.detail", grid=grid)
```

```jinja
{% from "components/grid.html" import data_grid %}
{{ data_grid(grid) }}
```

`sync_url=False` stops the grid writing its state to the page URL.

> [!NOTE]
> `build_grid` is not yet exported from `lattice.api`, so apps cannot use it.
> It will be added when the first app needs it.

## Home tiles and Ctrl+J

```python
TILES = [HomeTile("Open tickets", GRID, view="open"),
         HomeTile("Assigned to me", GRID, view="mine", tone="accent")]
```

A tile counts the grid's rows through its query, so the count respects the same
roles and row scoping. A click opens the grid with that view.

`palette=Palette(title, href, subtitle, icon)` makes rows findable from Ctrl+J;
see [Ctrl+J search](search.md).
