"""Permissions (ADR 0009): what a user may do, declared by apps, granted through roles.

An app declares its permissions in its manifest:

    Permission("showcase.claims.manage", "Handle claims",
               "Assign claims to zones and surveyors, set priority, record inspections, "
               "assessments and field reports, and run the intake simulator.",
               default_roles=("editor",))

Every check names a permission, never a role: `require("showcase.claims.manage")` on a
route, `permission="showcase.claims.manage"` on a NavNode, GridSpec or Action, and
`current_user.can("showcase.claims.manage")` in a template.

The catalogue (which permissions exist) comes from the code. Which role has
which permission is data in lattice.role_permission, edited in Administration ›
Roles. `lattice migrate` records each new permission and grants it to its
`default_roles` once; administrators decide after that.

The admin role has every permission, always.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lattice.kernel.database import Db
from lattice.kernel.queries import SQL

_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


class BadPermission(ValueError):
    """A permission is declared twice, badly named, or outside its app's namespace."""


@dataclass(frozen=True)
class Permission:
    key: str                                   # "{app}.{area}.{verb}", e.g. "showcase.claims.manage"
    label: str                                 # shown in Administration › Roles
    description: str = ""                      # one sentence: what it allows
    default_roles: tuple[str, ...] = ()        # granted once, when first migrated


CATALOGUE: dict[str, Permission] = {}


def reset() -> None:
    CATALOGUE.clear()


def register(permissions: list[Permission], prefix: str) -> None:
    """Add an app's permissions. `prefix` is "{app key}." ("lattice." for Lattice's own)."""
    for p in permissions:
        if not _KEY.match(p.key):
            raise BadPermission(f"Permission {p.key!r}: use dotted lower_case words, "
                                "e.g. 'showcase.claims.manage'")
        if not p.key.startswith(prefix):
            raise BadPermission(f"Permission {p.key!r} must start with {prefix!r}")
        if p.key in CATALOGUE:
            raise BadPermission(f"Permission {p.key!r} is declared twice")
        CATALOGUE[p.key] = p


def sync(db: Db) -> list[str]:
    """Record permissions new to the database and grant their default roles, once.

    Returns the keys that were new. Run by `lattice migrate`.
    """
    known = {r["key"] for r in db.all(SQL.permissions.known)}
    new = [p for key, p in sorted(CATALOGUE.items()) if key not in known]
    for p in new:
        db.run(SQL.permissions.record, key=p.key)
        db.run(SQL.permissions.grant_defaults, permission=p.key, roles=list(p.default_roles))
    return [p.key for p in new]
