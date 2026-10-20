"""docs/public_contract.md matches the code and a migrated database."""

import inspect
import re
from pathlib import Path

from sqlalchemy import text

import refdata

DOC = (Path(__file__).parents[1] / "docs" / "public_contract.md").read_text(encoding="utf-8")


def _table(heading: str) -> list[list[str]]:
    section = DOC.split(heading, 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    rows = [[c.strip() for c in line.strip("|").split("|")] for line in section.splitlines()
            if line.startswith("|") and not re.match(r"^\|[-|]+\|$", line)]
    return rows[1:]


def test_python_names():
    for name, kind, params in _table("## Python names"):
        obj = getattr(refdata, name)
        if kind == "function":
            assert list(inspect.signature(obj).parameters) == [p.strip() for p in params.split(",")]
    assert {n for n, _, _ in _table("## Python names")} == set(refdata.__all__) - {"__version__"}


def test_tables_have_exactly_the_listed_columns(conn):
    listed = [(c, t) for c, t in _table("### ref.place")]
    actual = [tuple(r) for r in conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'ref' AND table_name = 'place' ORDER BY ordinal_position"))]
    assert actual == listed
