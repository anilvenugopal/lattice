"""User lookup and creation. Every caller (admin UI, SSO, scripts, tests) goes through here."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lattice.kernel.auth.passwords import hash_password
from lattice.kernel.models import Role, User, UserRole


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))


def options(db: Session, _user=None) -> list[tuple[str, str]]:
    """Active users as (id, name) choices for selects and filters."""
    rows = db.execute(select(User.id, User.display_name).where(User.is_active.is_(True))
                      .order_by(User.display_name)).all()
    return [(str(r.id), r.display_name) for r in rows]


def role_codes(db: Session) -> set[str]:
    return set(db.scalars(select(Role.code)))


def create(db: Session, email: str, display_name: str, *, password: str | None = None,
           roles=(), must_change_password: bool = False, oidc_subject: str | None = None,
           is_active: bool = True) -> User:
    """Add a user (flushed, not committed). Unknown role codes are ignored."""
    valid = role_codes(db)
    user = User(email=normalize_email(email), display_name=display_name.strip(),
                password_hash=hash_password(password) if password else None,
                must_change_password=must_change_password, oidc_subject=oidc_subject,
                is_active=is_active)
    user.roles = [UserRole(role_code=r) for r in dict.fromkeys(roles) if r in valid]
    db.add(user)
    db.flush()
    return user
