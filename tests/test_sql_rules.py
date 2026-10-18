"""The plain-SQL rules (step 2 plan), checked over the whole repository.

1. Every named query is used by some code, and every query the code names exists.
2. Every named query is valid SQL for the schema: EXPLAIN accepts it.
3. SQL statements appear only in .sql files, apart from the two modules that build
   SQL (the grid engine and the migration runner) and the test database setup.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from sqlalchemy import text

import lattice_demo
from lattice.kernel.sql import sql_queries

ROOT = Path(__file__).parents[1]
CODE = [ROOT / "lattice", ROOT / "apps", ROOT / "hosts", ROOT / "tests"]
LATTICE_SQL = (ROOT / "lattice" / "sql").resolve()
BUILDS_SQL = {"lattice/kernel/migrate.py", "lattice/components/grid/engine.py",
              "lattice/testing.py", "tests/test_database.py", "tests/test_sql_rules.py"}
_STATEMENT = re.compile(r"\b(SELECT\s.+\sFROM|INSERT\s+INTO|UPDATE\s+\S+\s+SET|DELETE\s+FROM|"
                        r"(CREATE|DROP|ALTER)\s+(TABLE|SCHEMA|INDEX|DATABASE))\b", re.S)
_PLACEHOLDER = re.compile(r"(?<![:\w]):([a-z_]\w*)")


def python_files():
    for folder in CODE:
        yield from (p for p in folder.rglob("*.py") if ".venv" not in p.parts)


def sql_folders() -> list[Path]:
    return sorted({p.parent.resolve() for folder in CODE for p in folder.rglob("sql/*.sql")})


def defined() -> set[tuple[Path, str, str]]:
    return {(folder, q.path.stem, q.key.rsplit(".", 1)[1])
            for folder in sql_folders() for q in sql_queries(folder)}


def _sql_queries_call(node) -> ast.Call | None:
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "sql_queries":
        return node
    return None


def _folder(call: ast.Call, path: Path) -> Path | None:
    try:
        return Path(eval(ast.unparse(call.args[0]), {"Path": Path, "__file__": str(path)})).resolve()
    except Exception:
        return None                             # a folder made at run time (tests' tmp_path)


def referenced() -> set[tuple[Path, str, str]]:
    """(folder, area, name) for every `SQL.area.name` (or `AREA.name`) the code uses."""
    used = set()
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases: dict[str, tuple[Path, str | None]] = {}
        for node in ast.walk(tree):
            # sql_queries(folder).area.name, used directly
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                    and (call := _sql_queries_call(node.value.value))
                    and (folder := _folder(call, path))):
                used.add((folder, node.value.attr, node.attr))
            if isinstance(node, ast.ImportFrom) and node.module == "lattice.kernel.queries":
                for name in node.names:
                    if name.name == "SQL":
                        aliases[name.asname or "SQL"] = (LATTICE_SQL, None)
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                continue
            value, area = node.value, None
            if isinstance(value, ast.Attribute) and _sql_queries_call(value.value):
                value, area = value.value, value.attr
            call = _sql_queries_call(value)
            if call is None:
                continue
            if folder := _folder(call, path):
                aliases[node.targets[0].id] = (folder, area)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            base = node.value
            if isinstance(base, ast.Name) and aliases.get(base.id, (None, None))[1]:
                folder, area = aliases[base.id]
                used.add((folder, area, node.attr))
            elif (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                  and base.value.id in aliases and aliases[base.value.id][1] is None):
                used.add((aliases[base.value.id][0], base.attr, node.attr))
    return used


def _show(keys) -> str:
    return ", ".join(f"{folder.relative_to(ROOT)}/{area}.sql:{name}" for folder, area, name in
                     sorted(keys))


def test_every_named_query_is_used():
    unused = defined() - referenced()
    assert not unused, f"Named queries no code uses (delete them): {_show(unused)}"


def test_every_query_the_code_names_exists():
    missing = {r for r in referenced() if r[0] in set(sql_folders())} - defined()
    assert not missing, f"Code names queries that do not exist: {_show(missing)}"


@pytest.fixture
def host_apps():
    return [lattice_demo.APP]


def test_every_named_query_is_valid_sql(db):
    failures = []
    for folder in sql_folders():
        for q in sql_queries(folder):
            values = dict.fromkeys(_PLACEHOLDER.findall(q.sql))
            try:
                db.conn.execute(text(f"EXPLAIN {q.sql}"), values)
            except Exception as exc:
                failures.append(f"{q.key} ({q.path.relative_to(ROOT)}:{q.line}): "
                                f"{str(exc).splitlines()[0]}")
    assert not failures, "Invalid named queries:\n" + "\n".join(failures)


def test_sql_lives_only_in_sql_files():
    found = []
    for path in python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in BUILDS_SQL:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef)
                      and n.body and isinstance(n.body[0], ast.Expr)
                      and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings and _STATEMENT.search(node.value)):
                found.append(f"{rel}:{node.lineno}")
    assert not found, "SQL written in Python; move it to a named query in sql/*.sql: " + \
        ", ".join(found)
