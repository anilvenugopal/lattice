"""Per-user preferences, stored as JSON values in user_preference.

Keys in DEFAULTS are the user-facing settings on Account > Preferences.
Grids store column visibility under "grid.<grid key>.hidden".
set_pref() writes in the caller's transaction.
"""

from __future__ import annotations

import json

from lattice.kernel.database import Db
from lattice.kernel.queries import SQL

PAGE_SIZES = (25, 50, 100, 200)

DEFAULTS: dict[str, object] = {
    "theme": "system",          # system | light | dark
    "density": "comfortable",   # comfortable | compact
    "page_size": PAGE_SIZES[1],
    "landing_page": "/",
    "time_format": "relative",  # relative | absolute
}

# Values keep their stored type (page_size is an int); forms submit strings and save()
# maps them back through these lists.
CHOICES: dict[str, list[tuple[object, str]]] = {
    "theme": [("system", "Match system"), ("light", "Light"), ("dark", "Dark")],
    "density": [("comfortable", "Comfortable"), ("compact", "Compact")],
    "page_size": [(n, f"{n} rows") for n in PAGE_SIZES],
    "time_format": [("relative", "Relative (3h ago)"), ("absolute", "Absolute (17 Oct 2026 14:05)")],
}


def load(db: Db, user_id: int) -> dict:
    return {r["key"]: r["value"] for r in db.all(SQL.preferences.for_user, user_id=user_id)}


def choice(key: str, submitted: str, choices=None):
    """The allowed value matching a submitted form string, or None."""
    return {str(v): v for v, _ in (choices or CHOICES[key])}.get(submitted)


def get(user, key: str):
    return user.prefs.get(key, DEFAULTS.get(key))


def set_pref(db: Db, user_id: int, key: str, value) -> None:
    db.run(SQL.preferences.save, user_id=user_id, key=key, value=json.dumps(value))
