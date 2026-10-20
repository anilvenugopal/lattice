---
title: Record pages
summary: The standard detail page for one row of a grid. Header with status and actions, properties, the app's panels and the record's history, from one RecordPage.
order: 24
keywords: record page detail page recordpage panel link properties header actions history timeline render_record_page
---

A record page shows one row of a grid as a full page. It is declared on the
grid and reuses it:

- **The row** is read through the grid's query, with the grid's permission. A
  record a user cannot see in the list is a 404 here too.
- **Properties** render with the grid's `Column` kinds: money, dates, users,
  badges.
- **The status badge** beside the title uses the status column's labels and
  tones.
- **Header buttons** are the grid's row actions that apply to this row. They
  run through the grid's action endpoint, with the same dialogs, permissions
  and audit events as in the list. After one runs, the page updates in place.
- **Activity** is the audit history of the grid's actions on this row.

```python
from lattice.api import Link, Panel, RecordPage, render_record_page

DETAIL = RecordPage(
    grid=GRID, nav_key="claims.claim", title="{claim_number} · {insured}",
    subtitle="{event} · {city}", status="status", crumb="{claim_number}",
    properties=["event_code", "cause", "severity", "priority", "estimate", "zone", "surveyor"],
    links=[Link("Open in claims system", "/showcase/claims-system/{claim_number}", icon="external")],
    panels=[Panel("lifecycle", "Status", "showcase/event_lifecycle.html", load=_lifecycle)],
)

@router.get("/claims/{claim_id}")
def claim_page(claim_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, DETAIL, claim_id)
```

The page's `NavNode` is hidden, with the list's node as its parent, as for
every detail page ([Pages and navigation](pages-and-navigation.md)).

## The page

| Field | Use |
|---|---|
| `grid` | The list's `GridSpec`: its query, columns, actions and permission |
| `nav_key` | The page's hidden `NavNode` |
| `title`, `subtitle` | Formatted with the row: `"{ref} · {title}"` |
| `status` | A column shown as a badge beside the title |
| `properties` | Column keys for the **Details** card, in order (`details_title` renames it) |
| `links` | Header buttons that open a page, such as the edit form |
| `panels` | The app's own sections; see below |
| `actions` | `False` hides the grid's actions |
| `history` | `False` hides **Activity** |
| `back` | **Back to list** target; default the grid's `path` |
| `crumb` | Breadcrumb text, formatted with the row; default the title |
| `reference_kind` | The record's reference kind (`"showcase.claim"`): brings other apps' panels, Attachments and Follow; see below |

`RecordPage` refuses a property or status that is not one of the grid's
columns.

**Which actions appear.** Every grid action the user may run, with a selection
(`single` or `multi`), whose `when` matches this row. An action that only opens
the row's own page (`href` equal to the grid's `row_href`) is left out.

**After an action.** The page fetches itself again and redraws. If the action
removed the record from the grid's query (deleted it, or moved it out of the
user's rows), the browser returns to the list.

## Panels

A panel is a card drawn by the app's own template:

```python
Panel("where", "Where", "showcase/event_map.html", load=_where, place="side", flush=True)

def _where(request: Request, db: Db, row: dict) -> dict:
    return {"map": build_map(request, MAP, linked=False,
                             fixed={"id": row["id"], "event_id": row["event_id"]})}
```

```jinja
{# showcase/event_map.html #}
{% from "components/map.html" import map_view %}
{{ map_view(values.map) }}
```

| Field | Use |
|---|---|
| `key` | Unique on the page |
| `label` | The card heading, formatted with the row |
| `template` | `"{app}/…html"`, rendered with `record` (the row), `page` and `values` |
| `load` | `(request, db, row) -> dict`: the panel's `values`, such as an embedded grid or a chart |
| `place` | `main` (left column, under Details), `side` (right column, above Activity) or `full` (full width, below) |
| `permission` | Who sees it; empty means everyone who can open the record |
| `flush` | No padding inside the card, for a grid |

## What a reference kind adds

Set `reference_kind` to the kind your app declares in `references=`, and the
page gains, with no other code:

| Addition | From |
|---|---|
| **Other apps' panels**: Comments, and any `RecordPanel` another app declares for your kind or for every kind | [Working across apps](working-across-apps.md) |
| **Attachments**: files on the record, with preview, download and removal | [Attachments and folders](attachments.md) |
| **Follow**: people choose to be notified about the record | [Notifications](notifications.md) |

Each checks access through your reference kind's resolver: if it returns
nothing for a user, they cannot see the record's comments, files or follow it.
