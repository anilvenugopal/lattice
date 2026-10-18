"""User lookup and creation. Every caller (admin UI, SSO, scripts, tests) goes through here.

A user is a dict from SQL.users.by_id / by_email: id, email, display_name,
password_hash, oidc_subject, is_active, must_change_password, created_at,
last_login_at, and roles (a list of role codes).
"""

from __future__ import annotations

from lattice.kernel.auth.passwords import hash_password
from lattice.kernel.database import Db
from lattice.kernel.queries import SQL


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def by_email(db: Db, email: str) -> dict | None:
    return db.first(SQL.users.by_email, email=normalize_email(email))


def by_id(db: Db, user_id: int) -> dict:
    """The user, or NotFound (a 404 in a route)."""
    return db.one(SQL.users.by_id, id=user_id)


def options(db: Db, _user=None) -> list[tuple[str, str]]:
    """Active users as (id, name) choices for selects and filters."""
    return [(r["value"], r["label"]) for r in db.all(SQL.users.options)]


def role_options(db: Db, _user=None) -> list[tuple[str, str]]:
    return [(r["code"], r["label"]) for r in db.all(SQL.users.role_options)]


def role_codes(db: Db) -> set[str]:
    return {code for code, _ in role_options(db)}


def create(db: Db, email: str, display_name: str, *, password: str | None = None,
           roles=(), must_change_password: bool = False, oidc_subject: str | None = None,
           is_active: bool = True) -> dict:
    """Add a user and return it. Unknown role codes are ignored."""
    user_id = db.value(SQL.users.create, email=normalize_email(email),
                       display_name=display_name.strip(),
                       password_hash=hash_password(password) if password else None,
                       must_change_password=must_change_password, oidc_subject=oidc_subject,
                       is_active=is_active)
    db.run(SQL.users.add_roles, user_id=user_id, roles=list(roles))
    return by_id(db, user_id)


def sign_in_methods(user: dict) -> str:
    methods = [label for present, label in ((user["password_hash"], "Password"),
                                             (user["oidc_subject"], "Single sign-on")) if present]
    return " and ".join(methods) or "None"
