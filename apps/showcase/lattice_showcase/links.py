"""How the showcase works with other apps (ADR 0011), without importing them.

- Its events and claims can be referenced: `urn:lattice:showcase.claim:42` resolves to
  the claim's number and status for any app's `ref()`.
- It listens for `comments.added`: a comment on a claim gives its desk handler a notice.
"""

from __future__ import annotations

from pathlib import Path

from lattice.api import (
    CloudEvent,
    Db,
    ReferenceKind,
    Resolved,
    parse,
    sql_queries,
)
from lattice_showcase import notices

QUERIES = sql_queries(Path(__file__).parent / "sql")


def resolve_event(db: Db, user, event_id: str) -> Resolved | None:
    if not event_id.isdigit():
        return None
    row = db.first(QUERIES.events.by_id, id=int(event_id))
    if row is None:
        return None
    from lattice_showcase.events import STAGE_TONES, STAGES
    return Resolved(f"{row['code']} · {row['name']}", f"/showcase/events/{row['id']}",
                    badge=dict(STAGES)[row["status"]], tone=STAGE_TONES[row["status"]])


def resolve_claim(db: Db, user, claim_id: str) -> Resolved | None:
    if not claim_id.isdigit():
        return None
    row = db.first(QUERIES.claims.by_id, id=int(claim_id))
    if row is None:
        return None
    from lattice_showcase.claims import STATUS_TONES, STATUSES
    return Resolved(row["claim_number"], f"/showcase/claims/{row['id']}",
                    badge=dict(STATUSES)[row["status"]], tone=STATUS_TONES[row["status"]])


REFERENCES = [ReferenceKind("showcase.event", "Event", resolve_event, icon="showcase:storm"),
              ReferenceKind("showcase.claim", "Claim", resolve_claim, icon="queue")]


def notify_handler(db: Db, event: CloudEvent) -> None:
    """comments.added on a claim: tell its handler, unless they wrote the comment."""
    ref = parse(event.subject)
    if ref.kind != "showcase.claim" or not ref.id.isdigit():
        return
    claim = db.first(QUERIES.claims.handler, id=int(ref.id))
    if not claim or not claim["handler_id"] or claim["handler_id"] == event.data.get("author_id"):
        return
    author = event.data.get("author", "Someone")
    notices.tell(db, claim["handler_id"],
                 f"{author} commented on {claim['claim_number']} · {claim['insured']}",
                 event.data.get("excerpt", ""), f"/showcase/claims/{ref.id}")
