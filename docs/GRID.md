# The standard grid

One component lists every kind of record: work queues, job runs, mailboxes,
users, audit events. A screen declares a `GridSpec` in Python; the grid package
supplies the behaviour. The model follows Foundry Workshop's object table: an
object set (the query) feeds a table, the selection feeds actions and a detail view.

## What every grid gets

| Capability | How the user reaches it |
|---|---|
| Search across `search` columns (every word must match) | Search box, `/` to focus |
| Filters with multi- or single-select options | Filter chips in the toolbar |
| Views (named filter presets) | Tabs above the toolbar, or sidebar links (`views_in_nav=True`) |
| Sort by any sortable column | Click the header; click again to reverse |
| Paging, page size (default from the user's preference) | Footer |
| Single, multi, range and page selection; "select all N matching" | Click, Ctrl/⌘-click, Shift-click, header checkbox, Ctrl+A, Space/X |
| Action bar enabled by selection size and row state | Appears when rows are selected |
| Row menu with the same actions | `⋯` at the end of the row |
| Confirm and input dialogs | `Action.confirm`, `Action.fields` |
| Side panel (table layout) or reading pane (split layout) | Click a row; ↑/↓ follows; Esc closes |
| Open full record | Double-click or Enter (`row_href`) |
| Column show/hide, saved per user | Columns menu |
| CSV export of the filtered rows | Download button |
| Live refresh | `poll_seconds` |
| URL holds the state | Copy the address bar to share a filtered view |
| Ctrl+J search provider with preview | `palette=Palette(title, href, subtitle, icon)` |
| Home page count tile | `HomeTile(label, GRID, view=..., filters=...)` in the manifest's `tiles=` |
| Audit event per row per action | Automatic |

## Declaring a grid

```python
# apps/helpdesk/lattice_helpdesk/tickets.py — an app with key "helpdesk"
from lattice.api import (Action, Column, EDITORS, Filter, GridSpec, Palette, View,
                         get_db, render_grid_page)

def query(db, user):
    # Labeled columns. Must include "id". This is the access boundary.
    return select(Ticket.id, Ticket.ref, Ticket.subject, Ticket.status,
                  User.display_name.label("assignee"), Ticket.opened_at) \
        .outerjoin(User, User.id == Ticket.assignee_id)

def close(ctx):                         # ctx.ids, ctx.rows, ctx.values, ctx.user, ctx.db
    ctx.db.execute(update(Ticket).where(Ticket.id.in_(ctx.ids)).values(status="closed"))
    return f"Closed {ctx.count} ticket(s)."   # str or ActionResult; do not commit

GRID = GridSpec(
    key="helpdesk.tickets", title="Tickets", path="/helpdesk/tickets", query=query,
    columns=[
        Column("ref", "Ref", kind="mono", required=True),
        Column("subject", "Subject", kind="strong"),
        Column("status", "Status", kind="badge", tones=STATUS_TONES, labels=STATUS_LABELS),
        Column("assignee", "Assignee", kind="user"),
        Column("opened_at", "Opened", kind="ago"),
    ],
    search=["ref", "subject", "assignee"],
    filters=[Filter("status", "Status", STATUSES)],
    views=[View("open", "Open", where={"status": ["new", "open"]}),
           View("mine", "Mine", where={"assignee_id": "$me"}), View("all", "All")],
    actions=[
        Action("new", "New ticket", scope="none", href="/helpdesk/tickets/new", tone="primary", icon="plus"),
        Action("close", "Close", handler=close, when={"status": ["new", "open"]},
               confirm="Close {count} ticket(s)?", roles=EDITORS),
    ],
    default_sort="-opened_at", row_href="/helpdesk/tickets/{id}",
    palette=Palette(title="{ref} · {subject}", href="/helpdesk/tickets/{id}"),
)

@router.get("/tickets")                  # mounted under /helpdesk by the host
def tickets(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, GRID, "tickets")

# In the app's AppManifest: grids=[GRID], routers=[router], nav=[NavNode("tickets", …)]
```

The grid key starts with the app key and a dot, and the path starts with the app's
prefix; `create_app` refuses to start otherwise.

A view's `where` and a filter's `key` refer to columns in the query, so
`assignee_id` must be selected too (add `hidden=True` columns or simply select it;
only keys in `columns` render).

## Reference

### Column kinds

`text`, `strong` (emphasised), `mono`, `number`, `money`, `percent`, `date`,
`datetime`, `ago` (relative or absolute per user preference), `badge` (with
`tones` and `labels`), `bool`, `tags` (comma-separated), `progress` (0–100),
`user` (avatar + name), `star` (toggle that runs `star_action`), `template`
(your partial, receives `row` and `col`).

Options: `secondary` (muted second line from another key), `href` (link,
formatted with the row), `hidden` (off until the user enables it), `required`
(cannot be hidden), `width`, `align`, `sortable`.

### Actions

| Field | Meaning |
|---|---|
| `scope` | `none` toolbar button, no selection · `single` exactly one row · `multi` one or more |
| `handler` | Runs on the server with the eligible rows. Returns `str` or `ActionResult(message, tone, refresh, clear_selection, redirect)` |
| `href` | Navigate instead; `{id}` is the selected row |
| `when` | Row eligibility, `{"status": ["failed"]}`. Enabled when at least one selected row qualifies; the server skips the others and says so |
| `fields` | Inputs collected in a dialog: `Field(name, label, kind=text|textarea|select|number|date, options, required, default)` |
| `confirm` | Confirmation text; `{count}` is replaced |
| `roles` | Who sees and may run it (checked on the server) |
| `tone`, `icon`, `in_row_menu` | Presentation |

Server-side helpers: `GridSpec.actions_for(user)` (role filter) and `Action.applies(row)`
(the `when` rule). The action endpoint, the panel and the page context all use them.

### Layouts and panels

- `layout="table"` (default). Clicking a row opens the side panel when `panel` is set,
  or when there is no `row_href`. Otherwise clicking selects and Enter/double-click opens `row_href`.
- `layout="split"`: list on the left, reading pane on the right (email pattern).
- `panel(db, user, row) -> dict` returns `{"template": "features/x_panel.html", **context}`.
  Without `panel`, the grid shows every column as a property list. Return
  `"refresh_grid": True` when opening the panel changed the row (e.g. mark as read).
- `app.grid.render.render_panel()` renders the panel. Ctrl+J calls it with `preview=True`,
  which hides actions and the close button and adds an Open button.
- Panel and detail templates show statuses with `badge_for(spec.column("status"), value)`.

### Endpoints (shared by all grids)

`GET /_grid/{key}/rows`, `GET /_grid/{key}/panel/{id}`, `POST /_grid/{key}/action/{action}`,
`POST /_grid/{key}/columns`, `GET /_grid/{key}/export.csv`. Apps do not
write list endpoints.

### Selection rules

- Search, filter or view changes clear the selection. Paging and sorting keep it.
- "Select all N matching" sends the filter state, not ids; the server re-runs the
  query (up to 10,000 rows).

### Embedding a grid in another page

```python
grid = build_grid(request, db, GRID, sync_url=False)
return render_page(request, "helpdesk/thing.html", "things.detail", grid=grid)
```
```jinja
{% from "components/grid.html" import data_grid %}{{ data_grid(grid) }}
```
