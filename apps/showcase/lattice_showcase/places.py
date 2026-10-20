"""Place search for the showcase's maps: US towns, counties and zip codes from refdata."""

from __future__ import annotations

import refdata
from lattice.api import Db


def find(db: Db, user, text: str) -> list[dict]:
    return refdata.search_places(db.conn, text)
