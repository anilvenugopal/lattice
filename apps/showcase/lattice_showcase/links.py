"""How the showcase works with other apps (ADR 0011), without importing them.

- Its events and claims can be referenced: `urn:lattice:showcase.claim:42` resolves to
  the claim's number and status for any app's `ref()`.

A claim's desk handler follows the claim (claims.take, cat_seed), so comments on it reach
them through Lattice's notifications (ADR 0016).
"""

from __future__ import annotations

from pathlib import Path

from lattice.api import Db, ReferenceKind, Resolved, sql_queries

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
