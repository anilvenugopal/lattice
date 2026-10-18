"""Server-side sessions.

The cookie holds a random token. The database stores only its SHA-256 hash
(`session_key()`), so the user_session table and admin screens never expose a
usable cookie value. `CurrentUser.session_id` is that hash.

create_session and the revoke_* helpers write in the caller's transaction, together
with its audit event.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field

from lattice.kernel.auth.roles import ADMIN
from lattice.kernel.config import settings
from lattice.kernel.database import Db
from lattice.kernel.display import initials
from lattice.kernel.queries import SQL
from lattice.kernel.services import preferences

COOKIE_NAME = "lattice_session"
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


def create_session(db: Db, user_id: int, ip: str, user_agent: str, method: str) -> str:
    """Create a session and return the cookie token."""
    token = secrets.token_urlsafe(32)
    db.run(SQL.sessions.create, id=session_key(token), user_id=user_id,
           max_hours=settings.session_max_hours, ip_address=(ip or "")[:45],
           user_agent=(user_agent or "")[:512], auth_method=method)
    db.run(SQL.users.signed_in, id=user_id)
    return token


def load_session(db: Db, token: str) -> CurrentUser | None:
    """The signed-in user, or None when the session is unknown, revoked, idle, expired or
    belongs to a deactivated user."""
    session_id = session_key(token)
    row = db.first(SQL.sessions.signed_in_user, id=session_id,
                   idle_minutes=settings.session_idle_minutes)
    if row is None:
        return None
    if row["stale"]:                       # write last_seen at most once a minute
        db.run(SQL.sessions.touch, id=session_id)
    return CurrentUser(
        id=row["id"], email=row["email"], display_name=row["display_name"],
        roles=tuple(row["roles"]), must_change_password=row["must_change_password"],
        has_password=row["has_password"], session_id=session_id,
        prefs=preferences.load(db, row["id"]),
    )


def revoke_sessions(db: Db, session_ids: list[str]) -> int:
    return db.run(SQL.sessions.revoke, ids=list(session_ids))


def revoke_user_sessions(db: Db, user_ids: list[int], keep: str | None = None) -> int:
    """End every session of these users, except `keep` (the caller's own)."""
    return db.run(SQL.sessions.revoke_for_users, user_ids=list(user_ids), keep=keep)


def active(db: Db, user_id: int) -> list[dict]:
    """A user's sessions that are neither revoked nor expired, most recently used first."""
    return db.all(SQL.sessions.active_for_user, user_id=user_id)
