"""Named SQL queries, loaded from a package's `sql/` folder.

Every SQL statement in Lattice and its apps lives in a `.sql` file, one file per
area, as named queries:

    -- name: by_email
    -- The user with this email (emails are stored lower-case).
    SELECT id, email, display_name FROM lattice.app_user WHERE email = :email;

Code refers to a query by area and name, never by its text:

    SQL = sql_queries(Path(__file__).parent / "sql")
    db.first(SQL.users.by_email, email=email)

Rules, checked when the folder is loaded (a broken file stops the host):
- every query starts with `-- name: <name>`, unique in its file;
- the next line is a `--` comment saying what the query does;
- the query has a body;
- no placeholder is followed by `::` (write `CAST(:x AS date)`; `:x::date` is not bound).

Values are bound with `:name` placeholders, never pasted into the SQL.
Each statement is sent with a comment naming it (`/* lattice_demo/work_items.grid */`),
so database logs show where a query comes from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import TextClause, text

_NAME = re.compile(r"^--\s*name:\s*(\S*)\s*$")
_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
_CAST_ON_PLACEHOLDER = re.compile(r"(?<![:\w]):([a-z_]\w*)::")


class SqlError(Exception):
    """A SQL file breaks a rule, or code asks for a query that does not exist."""


@dataclass(frozen=True)
class Query:
    key: str                      # "lattice_demo/work_items.grid"
    sql: str                      # the body, as written in the file
    description: str
    path: Path
    line: int
    statement: TextClause = field(repr=False, compare=False)


class Area:
    """The queries of one file, as attributes: `SQL.users.by_email`."""

    def __init__(self, path: Path, queries: dict[str, Query]):
        self._path = path
        self._queries = queries

    def __getattr__(self, name: str) -> Query:
        try:
            return self._queries[name]
        except KeyError:
            raise SqlError(f"{self._path}: no query named {name!r}") from None

    def __iter__(self):
        return iter(self._queries.values())


class Queries:
    """Every area of one `sql/` folder: `SQL.users`, `SQL.sessions`…"""

    def __init__(self, folder: Path, areas: dict[str, Area]):
        self._folder = folder
        self._areas = areas

    def __getattr__(self, name: str) -> Area:
        try:
            return self._areas[name]
        except KeyError:
            raise SqlError(f"{self._folder}: no file {name}.sql") from None

    def __iter__(self):
        return (q for area in self._areas.values() for q in area)


def parse(path: Path, owner: str) -> dict[str, Query]:
    """The named queries in one file. `owner` labels them in logs ("lattice", "lattice_demo")."""
    lines = path.read_text(encoding="utf-8").splitlines()
    starts = [(i, m.group(1)) for i, line in enumerate(lines) if (m := _NAME.match(line))]
    if not starts:
        raise SqlError(f"{path}: no queries (each starts with '-- name: <name>')")
    if any(line.strip() and not line.lstrip().startswith("--") for line in lines[:starts[0][0]]):
        raise SqlError(f"{path}: SQL before the first '-- name:' line")
    queries: dict[str, Query] = {}
    for n, (start, name) in enumerate(starts):
        where = f"{path}:{start + 1}"
        if not _IDENT.match(name):
            raise SqlError(f"{where}: query name {name!r} must be lower_case_with_underscores")
        if name in queries:
            raise SqlError(f"{where}: query {name!r} is defined twice")
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        block = lines[start + 1:end]
        comments = []
        while block and block[0].lstrip().startswith("--"):
            comments.append(block.pop(0).lstrip()[2:].strip())
        if not any(comments):
            raise SqlError(f"{where}: query {name!r} needs a '--' comment saying what it does")
        body = "\n".join(block).strip().rstrip(";").strip()
        if not body:
            raise SqlError(f"{where}: query {name!r} has no SQL")
        if m := _CAST_ON_PLACEHOLDER.search(body):
            raise SqlError(f"{where}: write CAST(:{m.group(1)} AS …), not :{m.group(1)}::…; "
                           "a placeholder followed by :: is not bound")
        key = f"{owner}/{path.stem}.{name}"
        queries[name] = Query(key=key, sql=body, description=" ".join(comments), path=path,
                              line=start + 1, statement=text(f"/* {key} */ {body}"))
    return queries


_LOADED: dict[Path, Queries] = {}


def sql_queries(folder: Path) -> Queries:
    """Load every `*.sql` file in `folder` (not its `schema/` migrations). Loaded once."""
    folder = Path(folder).resolve()
    if folder not in _LOADED:
        if not folder.is_dir():
            raise SqlError(f"{folder}: no such folder")
        owner = folder.parent.name
        areas = {}
        for path in sorted(folder.glob("*.sql")):
            if not _IDENT.match(path.stem):
                raise SqlError(f"{path}: file names must be lower_case_with_underscores")
            areas[path.stem] = Area(path, parse(path, owner))
        _LOADED[folder] = Queries(folder, areas)
    return _LOADED[folder]
