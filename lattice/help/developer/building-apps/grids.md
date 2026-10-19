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
| Saved views: a user's own search, filters and sort, optionally shared | The Views menu in the toolbar |
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

A grid is a named query, which returns the rows, and a `GridSpec`, which
describes the list.

```sql
-- apps/helpdesk/lattice_helpdesk/sql/tickets.sql — an app with key "helpdesk"
-- Tickets: customer requests from opening to close.

-- name: grid
-- Every ticket with its assignee's name. Must select id. This is the access boundary.
SELECT t.id, t.ref, t.subject, t.status, t.assignee_id,
       u.display_name AS assignee, t.opened_at
FROM helpdesk.ticket t
LEFT JOIN lattice.app_user u ON u.id = t.assignee_id;

-- name: close
-- Close tickets.
UPDATE helpdesk.ticket SET status = 'closed' WHERE id = ANY(:ids);
```

```python
# apps/helpdesk/lattice_helpdesk/tickets.py
from pathlib import Path

from fastapi import APIRouter, Depends, Request

from lattice.api import (Action, Column, Db, Filter, GridSpec, Palette, View,
                         csrf_protect, get_db, render_grid_page, sql_queries)

SQL = sql_queries(Path(__file__).parent / "sql").tickets
STATUSES = [("new", "New"), ("open", "Open"), ("closed", "Closed")]
STATUS_TONES = {"new": "info", "open": "warning", "closed": "success"}


def close(ctx):
    ctx.db.run(SQL.close, ids=ctx.ids)
    return f"Closed {ctx.count} ticket(s)."     # a str or an ActionResult


GRID = GridSpec(
    key="helpdesk.tickets", title="Tickets", path="/helpdesk/tickets", query=SQL.grid,
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
               tone="primary", icon="plus", permission="helpdesk.tickets.edit"),
        Action("close", "Close", handler=close, when={"status": ["new", "open"]},
               confirm="Close {count} ticket(s)?", permission="helpdesk.tickets.edit"),
    ],
    default_sort="-opened_at",
    row_href="/helpdesk/tickets/{id}",
    palette=Palette(title="{ref} · {subject}", href="/helpdesk/tickets/{id}"),
)

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/tickets")                  # mounted under /helpdesk by the host
def tickets(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "tickets")
```

In the manifest: `grids=[GRID]`, `routers=[router]`, `sql=HERE / "sql"` and a
`NavNode` for `tickets`.

`create_app` refuses to start unless the grid key starts with the app key and a
dot (`helpdesk.`), and the path starts with the app's prefix (`/helpdesk`).

## The query

`query` is a named query (see [Data and audit](data-and-audit.md)). Each
column it selects is a row key: `Column`, `search`, `Filter`, `View`, `when`,
`Palette` and URL templates such as `{id}` all refer to these keys.

- **It must select `id`.** Selection, actions, panels and links use it.
- **Filter and view keys must be selected.** `View("mine", where={"assignee_id": "$me"})`
  needs `assignee_id` in the select. It does not need a `Column`; only keys in
  `columns` are shown.
- **It is the access boundary.** Filter out rows the user may not see here. The
  query may use `:user_id`, the signed-in user, as the demo Inbox does:
  `WHERE m.owner_id = :user_id`. Paging, panels, actions, export, tiles and
  Ctrl+J all run through it, so a row the query does not return cannot be
  reached any other way.

`$me` in a view's `where` is replaced with the signed-in user's id.

## Where the rows come from

A grid's rows come from **one SQL query that you write**. Lattice treats the
query as a box: it wraps it as a subquery, then adds the search, filters, view,
sort and paging on top:

```sql
SELECT g.* FROM ( <your query> ) AS g
WHERE <view> AND <filters> AND <search>
ORDER BY <sort>, g.id
LIMIT <page size> OFFSET <start>
```

So the query can be as complex as SQL allows, and every column it returns can
be shown, searched, filtered and sorted. Postgres merges the wrapping away
before it runs, so it costs nothing (see [Grid performance](grid-performance.md)).

**Joins.** Join as many tables as you need. The Work Queue joins the users
table to show each item's owner by name (`apps/demo/lattice_demo/sql/work_items.sql`).

**Lookups, counts and computed values.** Anything SQL can compute becomes a
column. For example, each customer with their number of open tickets and a
computed health label:

```sql
-- name: customers_grid
-- Customers with their region, open ticket count and a health label.
SELECT c.id, c.name, r.name AS region,
       COALESCE(o.open_count, 0) AS open_tickets,
       CASE WHEN COALESCE(o.open_count, 0) > 10 THEN 'busy' ELSE 'ok' END AS health
FROM helpdesk.customer c
JOIN helpdesk.region r ON r.id = c.region_id
LEFT JOIN (SELECT customer_id, count(*) AS open_count FROM helpdesk.ticket
           WHERE status IN ('new', 'open') GROUP BY customer_id) o ON o.customer_id = c.id;
```

`region`, `open_tickets` and `health` are ordinary columns to the grid: a
`Filter("health", …)`, `View(where={"region": [...]})`, sorting by
`open_tickets` and searching `region` all work. Administration › Users does
the same with each user's roles.

**The limits:**

- **Rows come from the database.** A grid cannot list rows from a web service
  or a Python list. Data sources for that are planned (step 5 in
  [Decisions and direction](../architecture/decisions.md)).
- **No per-row Python.** You cannot run Python on every row before it is
  shown. Do the work in SQL. Three things help with display:
  - a column's `labels` turn stored values into text;
  - a `template` column draws a cell from the row's values;
  - the side `panel` function runs Python for the one row opened, so it can
    look anything up, even in another system.
- **One database.** Every app's schema is in one database, so any table can be
  joined.
- **Speed.** The query runs for every page, count and export, under a time
  limit (`LATTICE_GRID_QUERY_TIMEOUT_SECONDS`). Index the columns you filter,
  sort and join on. See [Grid performance](grid-performance.md) for what the
  database runs and what gets expensive on large tables.

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
| `permission` | Who sees and may run it; the server checks again. Empty: everyone who can see the grid |
| `tone`, `icon`, `in_row_menu` | Presentation |

When an action runs, the server:

1. checks the user has the action's `permission`;
2. reloads the selected rows through the query (up to 10,000 for "select all");
3. drops the rows that fail `when`;
4. calls the handler;
5. writes one audit event per row (`{grid key}.{action key}`).

All of it is one transaction, saved when the request succeeds.

**If the handler raises, nothing is saved:** neither its changes nor the audit events.

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
            "ticket": db.one(SQL.by_id, id=row["id"]),
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
| `GET /_grid/{key}/views` | The user's saved views and those shared with everyone |
| `POST /_grid/{key}/views` | Saves the current state as a view (JSON: `name`, `state`, `shared`) |
| `POST /_grid/{key}/views/{id}` | Renames, re-saves or shares one of the user's views |
| `POST /_grid/{key}/views/{id}/delete` | Deletes a view: the owner, or a holder of `lattice.views.share` for shared views |

Saved views need nothing from the app. A view stores the grid's URL state
(tab, search, filters, sort and page size) in `lattice.grid_view`, so every
grid has them. A view that names a filter or column the grid no longer has
simply loses that part.

## Embedding a grid in another page

`render_grid_page` makes a page that is only a grid. To put a grid **inside**
another page, build it with `build_grid` and place it with the `data_grid`
macro. The usual reason is a record page that lists related records: a
customer's tickets, a job's runs, all items from one account.

Embedded, it is the full grid: search, views, sorting, paging, selection,
actions, the side panel and export all work.

### Fix it to the record with `fixed`

On a customer's page you want that customer's tickets, not every ticket. Pass
`fixed`: column → value. The grid shows only matching rows, on every request,
and the user cannot remove it.

```python
from lattice.api import build_grid, render_page


@router.get("/customers/{customer_id}")
def customer(customer_id: int, request: Request, db: Db = Depends(get_db)):
    customer = get_visible_customer(db, request.state.user, customer_id)   # 404 if not visible
    tickets = build_grid(request, db, tickets_module.GRID, sync_url=False,
                         fixed={"customer_id": customer.id})
    return render_page(request, "helpdesk/customer.html", "customers.detail",
                       customer=customer, tickets=tickets, crumb=customer.name)
```

```jinja
{% from "components/grid.html" import data_grid %}
…
{% call card("Tickets", flush=True) %}{{ data_grid(tickets) }}{% endcall %}
```

A working example is in the demo: open any work item. Under its details,
**All work items from {account}** is the Work Queue grid fixed to that item's
account (`detail()` in `apps/demo/lattice_demo/work_items.py`).

### What `fixed` does

- **Columns.** Each key is a column of the grid's query: the label in its
  `select`. It does not need to be a `Column` or a `Filter`; select it in the
  query and it can be fixed. A key the query does not have is an error.
- **Values.** A single value, or a list for "any of these":
  `fixed={"status": ["new", "open"]}`.
- **Everywhere.** It applies to the rows, the counts and paging, "select all N
  matching", actions run on all matching rows, and CSV export.
- **On top of the user's choices.** The user's search, filters and views
  narrow further inside it.
- **No filter chip.** A filter chip for a fixed column is hidden, since it
  could only conflict.

### `sync_url=False`

A full grid page keeps its state in the address bar, so a link reopens the
same view. An embedded grid must not. The page's URL belongs to the page.
With `sync_url=False` the grid starts from its defaults (first view, default
sort, first page) and never writes to the URL. Always pass it when embedding.

### Using it well

- **Access.** `fixed` narrows what is shown; it is **not access control**. It
  travels with each request from the browser, and a user could edit it. The
  grid's query still decides what a user may see, so they could only ever
  reach rows they could see on the grid's own page. Keep row access in the
  query, as always.
- **Reuse the grid.** Embed the app's existing grid rather than declaring a
  second one, so columns, actions and labels stay the same in both places.
  Declare a separate `GridSpec` only when the embedded list needs different
  columns or actions. Give it its own key, for example
  `helpdesk.customer_tickets`.
- **Hide the fixed column.** On a customer's page, a Customer column says the
  same thing in every row. Leave it out of the grid's `columns`, or set
  `hidden=True`, and select it in the query only for fixing.
- **Use `flush=True`** on the card, so the grid sits edge to edge.
- **One per grid key.** A page can embed several different grids, but the same
  grid only once.
- **After an action,** the embedded grid refreshes itself, like a full grid
  page. If the action changes the record the page shows, return
  `ActionResult(redirect=…)` to reload the page.

## Home tiles and Ctrl+J

```python
TILES = [HomeTile("Open tickets", GRID, view="open"),
         HomeTile("Assigned to me", GRID, view="mine", tone="accent")]
```

A tile counts the grid's rows through its query, so the count respects the same
roles and row scoping. A click opens the grid with that view.

`palette=Palette(title, href, subtitle, icon)` makes rows findable from Ctrl+J;
see [Ctrl+J search](search.md).
