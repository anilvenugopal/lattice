"""refdata's named queries: `-- name: x`, a `--` description line, then the statement
(the file format Lattice and geoengine use, read by this small loader)."""

from __future__ import annotations

import re
from pathlib import Path

_NAME = re.compile(r"^--\s*name:\s*(\S+)\s*$")
FOLDER = Path(__file__).parent / "sql"


def load(area: str) -> dict[str, str]:
    """Each named statement's SQL text, with a comment naming it."""
    queries: dict[str, list[str]] = {}
    current = None
    for line in (FOLDER / f"{area}.sql").read_text(encoding="utf-8").splitlines():
        m = _NAME.match(line)
        if m:
            current = m.group(1)
            queries[current] = []
        elif current and not (line.startswith("--") and not queries[current]):
            queries[current].append(line)
    return {name: f"/* refdata/{area}.{name} */ " + "\n".join(body).strip().rstrip(";")
            for name, body in queries.items()}
