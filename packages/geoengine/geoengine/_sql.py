"""geoengine's named queries: `-- name: x`, a `--` description line, then the statement.

The same file format Lattice uses, read by geoengine's own small loader so the package
depends on nothing but SQLAlchemy.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import TextClause, text

_NAME = re.compile(r"^--\s*name:\s*(\S+)\s*$")
FOLDER = Path(__file__).parent / "sql"


def load(area: str) -> dict[str, TextClause]:
    queries: dict[str, list[str]] = {}
    current = None
    for line in (FOLDER / f"{area}.sql").read_text(encoding="utf-8").splitlines():
        m = _NAME.match(line)
        if m:
            current = m.group(1)
            queries[current] = []
        elif current and not (line.startswith("--") and not queries[current]):
            queries[current].append(line)
    return {name: text(f"/* geoengine/{area}.{name} */ " + "\n".join(body).strip().rstrip(";"))
            for name, body in queries.items()}
