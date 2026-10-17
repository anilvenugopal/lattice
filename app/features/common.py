"""Lookups shared by feature modules."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def user_options(db: Session, _user=None) -> list[tuple[str, str]]:
    rows = db.execute(select(User.id, User.display_name).where(User.is_active.is_(True))
                      .order_by(User.display_name)).all()
    return [(str(r.id), r.display_name) for r in rows]

