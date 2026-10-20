"""Named places to search by: US towns, counties and zip codes (Census gazetteer, 2024).

`search_places(conn, "Lake Charles, LA")` finds places by the start of their name,
optionally narrowed by a state after a comma, or by a zip code.
"""

from __future__ import annotations

import csv
import gzip
import re
from pathlib import Path

from sqlalchemy import Connection
from sqlalchemy import text as statement

from refdata._sql import load

SQL = load("places")
DATA = Path(__file__).parent / "data" / "us_places.csv.gz"
_STATE = re.compile(r"^(.*?),\s*([A-Za-z]{2})$")


def load_places(conn: Connection) -> int:
    """Load the bundled places if none are loaded; returns how many were added."""
    if conn.execute(statement(SQL["count"])).scalar():
        return 0
    added = 0
    with gzip.open(DATA, "rt", encoding="utf-8") as f, conn.connection.cursor() as cur, \
            cur.copy(SQL["copy"]) as copy:
        for row in csv.DictReader(f):
            copy.write_row((row["kind"], row["name"], row["state"], float(row["lon"]),
                            float(row["lat"]), float(row["sqmi"])))
            added += 1
    return added


def label(place: dict) -> str:
    return f"ZIP {place['name']}" if place["kind"] == "zip" else f"{place['name']}, {place['state']}"


def search_places(conn: Connection, text: str, limit: int = 8) -> list[dict]:
    """Places matching typed text ("Lake Ch", "Lake Charles, LA", "Harris County", "77002"),
    each as {kind, name, state, lon, lat, label}."""
    text = " ".join(text.split())
    if len(text) < 2:
        return []
    name, state = text, ""
    if m := _STATE.match(text):
        name, state = m.group(1).strip(), m.group(2)
    prefix = name.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    rows = conn.execute(statement(SQL["search"]), {"prefix": prefix, "name": name, "state": state,
                                           "limit": limit}).mappings()
    return [{**r, "label": label(r)} for r in rows]
