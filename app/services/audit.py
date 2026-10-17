"""Audit trail.

record() adds an event to the caller's transaction; the caller commits.
Events about a person use target_type "users" and the user id, the same as the
users grid, so one history() query finds every event for that person.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, User, utcnow


def record(db: Session, actor_id: int | None, action: str, summary: str,
           target_type: str = "", target_id: str | int = "", detail: dict | None = None,
           at: datetime | None = None) -> None:
    """`at` lets one bulk action stamp all its per-row events with the same time."""
    db.add(AuditEvent(actor_id=actor_id, action=action, summary=summary[:512],
                      target_type=target_type, target_id=str(target_id), detail=detail,
                      at=at or utcnow()))


def _timeline_select():
    """Rows with .action .summary .at .actor — the shape the timeline macro renders."""
    return (select(AuditEvent.action, AuditEvent.summary, AuditEvent.at,
                   func.coalesce(func.max(User.display_name), "System").label("actor"))
            .outerjoin(User, User.id == AuditEvent.actor_id))


def history(db: Session, target_type: str | None = None, target_id=None, *,
            actor_id: int | None = None, limit: int = 20):
    """Newest events about one target and/or by one actor. One line per bulk action."""
    conds = []
    if target_type is not None:
        conds.append((AuditEvent.target_type == target_type)
                     & (AuditEvent.target_id == str(target_id)))
    if actor_id is not None:
        conds.append(AuditEvent.actor_id == actor_id)
    stmt = _timeline_select()
    if conds:
        stmt = stmt.where(or_(*conds))
    # Per-row events of one bulk action share actor, action, summary and time.
    return db.execute(
        stmt.group_by(AuditEvent.actor_id, AuditEvent.action, AuditEvent.summary, AuditEvent.at)
        .order_by(AuditEvent.at.desc()).limit(limit)).all()
