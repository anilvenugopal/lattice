"""Audit trail.

record() writes in the caller's transaction. Events about a person use target_type
"users" and the user id, the same as the users grid, so one history() query finds
every event for that person.
"""

from __future__ import annotations

from lattice.kernel.database import Db
from lattice.kernel.queries import SQL


def record(db: Db, actor_id: int | None, action: str, summary: str,
           target_type: str = "", target_id: str | int = "", detail: dict | None = None) -> None:
    db.run(SQL.audit.record, actor_id=actor_id, action=action, summary=summary[:512],
           target_type=target_type, target_id=str(target_id), detail=detail)


def record_many(db: Db, actor_id: int | None, action: str, summary: str, target_type: str,
                target_ids: list, detail: dict | None = None) -> None:
    """One event per target, in one statement. Events in one transaction share their time."""
    db.run(SQL.audit.record_many, actor_id=actor_id, action=action, summary=summary[:512],
           target_type=target_type, target_ids=[str(t) for t in target_ids], detail=detail)


def history(db: Db, target_type: str | None = None, target_id=None, *,
            actor_id: int | None = None, limit: int = 20) -> list[dict]:
    """Newest events about one target and/or by one actor, as the timeline macro renders them."""
    return db.all(SQL.audit.history, target_type=target_type,
                  target_id=None if target_id is None else str(target_id),
                  actor_id=actor_id, limit=limit)
