"""docs/public_contract.md is true: every listed name, table column and function exists."""

import inspect
import re
from pathlib import Path

from sqlalchemy import text

import geoengine

DOC = (Path(__file__).parents[1] / "docs" / "public_contract.md").read_text(encoding="utf-8")


def section(title: str) -> str:
    return DOC.split(f"## {title}", 1)[1].split("\n## ", 1)[0]


def rows(block: str) -> list[list[str]]:
    """The body rows of the markdown tables in a block (header and rule lines skipped)."""
    lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    out = []
    for i, line in enumerate(lines):
        is_header = i + 1 < len(lines) and lines[i + 1].startswith("|---")
        if not is_header and not line.startswith("|---"):
            out.append([c.strip() for c in line.strip("|").split("|")])
    return out


def test_python_names():
    for name, kind, params in rows(section("Python names")):
        obj = getattr(geoengine, name)
        if kind == "function":
            wanted = [p.strip() for p in params.split(",")]
            assert list(inspect.signature(obj).parameters)[:len(wanted)] == wanted, name
    listed = {r[0] for r in rows(section("Python names"))}
    assert listed == set(geoengine.__all__) - {"__version__"}


def test_tables_have_exactly_the_listed_columns(conn):
    for table in ("layer", "feature", "point"):
        block = section("Tables in schema geo").split(f"### geo.{table}", 1)[1].split("###")[0]
        listed = {name: kind for name, kind in rows(block)}
        actual = {r.column_name: r.data_type if r.data_type != "USER-DEFINED" else r.udt_name
                  for r in conn.execute(text(
                      "SELECT column_name, data_type, udt_name FROM information_schema.columns "
                      "WHERE table_schema = 'geo' AND table_name = :t"), {"t": table})}
        assert actual == listed, table


def test_sql_functions_exist(conn):
    for signature, _returns in rows(section("SQL functions")):
        name = re.match(r"geo\.(\w+)\(", signature).group(1)
        assert conn.execute(text("SELECT count(*) FROM pg_proc p JOIN pg_namespace n "
                                 "ON n.oid = p.pronamespace WHERE n.nspname = 'geo' "
                                 "AND p.proname = :n"), {"n": name}).scalar() == 1


def test_closed_sets():
    sets = dict(rows(section("Closed sets")))
    assert sets["quality tier"].split(", ") == [t.code for t in geoengine.TIERS]
