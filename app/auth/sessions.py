"""Server-side sessions.

The cookie holds a random token. The database stores only its SHA-256 hash
(`session_key()`), so the user_session table and admin screens never expose a
usable cookie value. `CurrentUser.session_id` is that hash.

create_session and the revoke_* helpers do not commit; the calling route commits
together with its audit event.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.auth.roles import ADMIN
from app.config import settings
from app.display import initials
from app.models import User, UserSession, utcnow
from app.services import preferences

COOKIE_NAME = "app_session"
AUTH_METHOD_LABELS = {"password": "Password", "oidc": "SSO"}


@dataclass(frozen=True)
class CurrentUser:
    id: int
    email: str
    display_name: str
    roles: tuple[str, ...]
    must_change_password: bool
    has_password: bool
    session_id: str
    prefs: dict = field(default_factory=dict)

    @property
    def is_admin(self) -> bool:
        return ADMIN in self.roles

    def has_any(self, roles) -> bool:
        """True when `roles` is empty or shares a role with the user."""
        return not roles or any(r in self.roles for r in roles)

    @property
    def initials(self) -> str:
        return initials(self.display_name, self.email)


def session_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, ip: str, user_agent: str, method: str) -> str:
    """Create a session and return the cookie token."""
    token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(UserSession(
        id=session_key(token), user_id=user.id, created_at=now, last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_max_hours),
        ip_address=(ip or "")[:45], user_agent=(user_agent or "")[:512], auth_method=method,
    ))
    user.last_login_at = now
    return token


def load_session(db: Session, token: str) -> CurrentUser | None:
    """Return the signed-in user, or None when the session is unknown, revoked, idle or expired."""
    session_id = session_key(token)
    now = utcnow()
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
    ).first()
    if row is None:
        return None
    sess, user = row
    idle_limit = sess.last_seen_at + timedelta(minutes=settings.session_idle_minutes)
    if not user.is_active or now > sess.expires_at or now > idle_limit:
        return None
    # Write last_seen at most once a minute to keep reads cheap.
    if (now - sess.last_seen_at).total_seconds() > 60:
        sess.last_seen_at = now
        db.commit()
    prefs = preferences.load(db, user.id)
    return CurrentUser(
        id=user.id, email=user.email, display_name=user.display_name,
        roles=tuple(user.role_codes), must_change_password=user.must_change_password,
        has_password=bool(user.password_hash), session_id=session_id, prefs=prefs,
    )


def revoke_session(db: Session, session_id: str) -> None:
    db.execute(update(UserSession).where(UserSession.id == session_id).values(revoked_at=utcnow()))


def revoke_user_sessions(db: Session, user_id: int, keep: str | None = None) -> int:
    stmt = (update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=utcnow()))
    if keep:
        stmt = stmt.where(UserSession.id != keep)
    return db.execute(stmt).rowcount


def is_active_clause():
    """SQL condition for a session that is neither revoked nor expired."""
    return and_(UserSession.revoked_at.is_(None), UserSession.expires_at > utcnow())


def active(db: Session, user_id: int | None = None):
    """Unrevoked, unexpired sessions, most recently used first; all users when user_id is None."""
    stmt = (select(UserSession)
            .where(is_active_clause())
            .order_by(UserSession.last_seen_at.desc()))
    if user_id is not None:
        stmt = stmt.where(UserSession.user_id == user_id)
    return db.scalars(stmt).all()
