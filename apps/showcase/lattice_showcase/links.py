"""How the showcase works with other apps (ADR 0011), without importing them.

- Its items and specs can be referenced: `urn:lattice:showcase.item:42` resolves to the
  item's reference, name and status for any app's `ref()`.
- It listens for `comments.added`: a comment on an item puts a message in the owner's
  Reading pane.
"""

from __future__ import annotations

from pathlib import Path

from lattice.api import (
    CloudEvent,
    Db,
    NotFound,
    ReferenceKind,
    Resolved,
    documents,
    parse,
    sql_queries,
)
from lattice_showcase import specs
from lattice_showcase.items import STATUS_TONES, STATUSES

QUERIES = sql_queries(Path(__file__).parent / "sql")


def resolve_item(db: Db, user, item_id: str) -> Resolved | None:
    if not item_id.isdigit():
        return None
    row = db.first(QUERIES.items.by_id, id=int(item_id))
    if row is None:
        return None
    return Resolved(f"{row['ref']} · {row['name']}", f"/showcase/items/{row['id']}",
                    badge=dict(STATUSES)[row["status"]], tone=STATUS_TONES[row["status"]])


def resolve_spec(db: Db, user, doc_id: str) -> Resolved | None:
    if not doc_id.isdigit():
        return None
    try:
        doc = documents.get(db, specs.SPEC, int(doc_id))
    except NotFound:
        return None
    return Resolved(doc["title"], f"/showcase/specs/{doc['id']}", subtitle="Spec")


def resolve_event(db: Db, user, event_id: str) -> Resolved | None:
    if not event_id.isdigit():
        return None
    row = db.first(QUERIES.events.by_id, id=int(event_id))
    if row is None:
        return None
    from lattice_showcase.events import STAGE_TONES, STAGES
    return Resolved(f"{row['code']} · {row['name']}", f"/showcase/events/{row['id']}",
                    badge=dict(STAGES)[row["status"]], tone=STAGE_TONES[row["status"]])


REFERENCES = [ReferenceKind("showcase.event", "Event", resolve_event, icon="showcase:storm"),
              ReferenceKind("showcase.item", "Item", resolve_item, icon="queue"),
              ReferenceKind("showcase.spec", "Spec", resolve_spec, icon="showcase:form")]


def notify_owner(db: Db, event: CloudEvent) -> None:
    """comments.added on an item: tell its owner, unless they wrote the comment."""
    ref = parse(event.subject)
    if ref.kind != "showcase.item" or not ref.id.isdigit():
        return
    item = db.first(QUERIES.items.owner, id=int(ref.id))
    if not item or not item["owner_id"] or item["owner_id"] == event.data.get("author_id"):
        return
    author = event.data.get("author", "Someone")
    db.run(QUERIES.inbox.notify, owner_id=item["owner_id"], sender_name=author,
           subject=f"{author} commented on {item['ref']} · {item['name']}",
           body=f"{event.data.get('excerpt', '')}\n\nOpen the item: /showcase/items/{ref.id}")
