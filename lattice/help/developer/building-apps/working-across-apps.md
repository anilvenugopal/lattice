---
title: Working across apps
summary: Apps cooperate without importing each other. References to records as URNs, panels on other apps' record pages, and CloudEvents between them.
order: 65
keywords: reference urn ref resolver referencekind record panel recordpanel event cloudevents publish subscribe integration
---

Apps never import each other: `make lint` fails if they do. They cooperate
through three contracts, each following a standard where one exists
([ADR 0011](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0011-integration-standards.md)):

| Contract | What it gives | Standard |
|---|---|---|
| **References** | A pointer to any record that any app can show as a link | URN |
| **Record panels** | A section one app adds to other apps' record pages | Lattice registry |
| **Events** | One app announces that something happened; others react | CloudEvents 1.0 |

The showcase and Comments use all of them: comment on any item, and its owner
gets a message in the showcase's Reading pane.

## References

A reference is a URN: `urn:lattice:{kind}:{id}`, such as
`urn:lattice:showcase.item:42`. The kind starts with the owning app's key. Store
and pass references as text; never as a foreign key into another app's
tables.

**The owning app declares each kind,** with a resolver that turns an id into
what a user sees:

```python
from lattice.api import ReferenceKind, Resolved

def resolve_item(db: Db, user, item_id: str) -> Resolved | None:
    row = db.first(SQL.items.by_id, id=int(item_id)) if item_id.isdigit() else None
    if row is None:
        return None
    return Resolved(f"{row['ref']} · {row['name']}", f"/showcase/items/{row['id']}",
                    badge=STATUS_LABELS[row["status"]], tone=STATUS_TONES[row["status"]])

APP = AppManifest(key="showcase", …, references=[ReferenceKind("showcase.item", "Item", resolve_item)])
```

**Return `None`** when the record is gone **or this user may not see it**: a
reference never shows a record its viewer couldn't open.

**Any template draws one** with `{{ ref(urn) }}`: the title linked to the
record, with its status badge, or "Item unavailable". It works in grid cells
(`kind="template"`), panels and pages.

| In Python | Does |
|---|---|
| `urn("showcase.item", 42)` | `"urn:lattice:showcase.item:42"` |
| `parse(value)` | A `Ref` with `.kind`, `.id`, `.app` and `.urn`; raises on anything else |
| `resolve_ref(db, user, value)` | The `Resolved`, or `None` |

## Record panels

An app adds a panel to other apps' record pages:

```python
from lattice.api import RecordPanel

PANEL = RecordPanel("comments.panel", "Comments", "comments/panel.html", kinds="*",
                    load=load_comments, permission="comments.read")

def load_comments(request: Request, db: Db, subject: Ref) -> dict:
    return {"comments": db.all(SQL.on_subject, subject=subject.urn)}

APP = AppManifest(key="comments", …, panels=[PANEL])
```

**A record page shows them** when it names its kind:

```python
DETAIL = RecordPage(grid=GRID, …, reference_kind="showcase.item")
```

Contributed panels follow the page's own. Each appears only to users with its
`permission`.

| Field | Use |
|---|---|
| `kinds` | The reference kinds it applies to, or `"*"` for every kind |
| `template` | Rendered with `subject` (the record's `Ref`) and `values` from `load` |
| `load` | `(request, db, subject) -> dict` |
| `place` | `side` (default), `main` or `full` |

A panel works from the reference, not the other app's row. To show the record
itself, use `ref(subject.urn)`.

## Events

**Declare what you publish, then publish it** in the request's transaction:

```python
APP = AppManifest(key="comments", …, publishes=["comments.added"])

db.publish("comments.added", subject=urn("showcase.item", 42),
           data={"comment_id": 7, "author_id": 3, "excerpt": "Valve looks worn."})
```

**Subscribe** in another app's manifest:

```python
def notify_owner(db: Db, event: CloudEvent) -> None:
    ref = parse(event.subject)
    …

APP = AppManifest(key="showcase", …, subscribes={"comments.added": notify_owner})
```

- **After the commit.** Subscribers run once the publishing request has
  committed. If the request fails, nothing was saved, so nothing is delivered.
- **Each subscriber in its own transaction.** One that raises is logged and
  undoes only its own work.
- **The event** is a CloudEvent: `type`, `source` (`/lattice/{host}/{app}`),
  `id`, `subject` (the record's URN), `time` and a small `data` dict.
  `event.to_dict()` is its standard JSON form.
- **No retries.** Delivery happens in the publishing process, right after the
  commit. A reaction that must not be missed reads state instead (below).

## Another process's state

Lattice reads no other system's event stream. To react to something another
process does, such as a Taskline run failing, read that system's published
views on a timer, for a time window, and remember what you have handled
([ADR 0012](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0012-taskline-ui-and-contract.md)).
A cursor over "everything after the last id" can miss rows that become
visible out of order; asking "what is the state now" cannot.

## What is checked when the host starts

- Reference kinds, panel keys and event types start with the app's key.
- Publishing a type no app declares fails.
- A subscription or panel naming another app in the host must name a type or
  kind that app declares. Naming an app the host doesn't run is allowed: it
  never applies.
