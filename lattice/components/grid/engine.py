"""Turns a GridSpec plus request parameters into SQL and rows.

`GridSpec.query` is a named query (a `.sql` file). The engine wraps it as a
subquery `g` and adds the view, filters, search, sort and paging around it:

    SELECT g.* FROM (<the named query>) AS g WHERE … ORDER BY … LIMIT … OFFSET …

This module and the migration runner are the only code in Lattice that builds SQL.
Column names come from the query itself (asked of Postgres once per query), and
values are always bound. The query may use `:user_id`, the signed-in user, to
scope rows.

Every read and every action goes through the query, so it is the grid's access
boundary: a row the query does not return cannot be shown, exported or acted on.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from math import ceil

from psycopg.errors import QueryCanceled
from psycopg.postgres import types as pg_types
from sqlalchemy import ColumnElement, String, and_, cast, column, false, func, or_, select, text
from sqlalchemy.exc import DBAPIError

from lattice.components.grid.spec import GridSpec
from lattice.kernel.config import settings
from lattice.kernel.database import Db
from lattice.kernel.services import preferences

PAGE_SIZES = preferences.PAGE_SIZES
DEFAULT_PAGE_SIZE = preferences.DEFAULTS["page_size"]
MAX_BULK = 10_000
MAX_EXPORT = 50_000


@dataclass
class GridQuery:
    """User-controlled grid state. Round-trips through the page URL."""

    q: str = ""
    sort: str = ""
    page: int = 1
    size: int = DEFAULT_PAGE_SIZE
    view: str = ""
    filters: dict[str, list[str]] = field(default_factory=dict)
    # Set by the page that embeds the grid (build_grid(fixed=…)), not by the user.
    # It travels as x_{key} parameters and narrows the query; it is not access control.
    fixed: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_params(cls, params, spec: GridSpec, default_size: int = DEFAULT_PAGE_SIZE):
        def as_int(name, default):
            try:
                return int(params.get(name) or default)
            except ValueError:
                return default

        size = as_int("size", default_size)
        filters = {}
        for flt in spec.filters:
            values = [v for v in params.getlist(f"f_{flt.key}") if v != ""]
            if values:
                filters[flt.key] = values
        fixed = {k[2:]: params.getlist(k) for k in params if k.startswith("x_")}
        view = params.get("view", "")
        if view and not spec.view(view):
            view = ""
        if not view and spec.views:
            view = spec.views[0].key
        return cls(
            q=(params.get("q") or "").strip(),
            sort=params.get("sort", ""),
            page=max(1, as_int("page", 1)),
            size=size if size in PAGE_SIZES else default_size,
            view=view,
            filters=filters,
            fixed=fixed,
        )

    def effective_sort(self, spec: GridSpec) -> str:
        """The sort in force: the user's, else the view's, else the grid default."""
        view = spec.view(self.view)
        return self.sort or (view.sort if view and view.sort else "") or spec.default_sort


@dataclass
class GridPage:
    rows: list[dict]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.size))

    @property
    def first(self) -> int:
        return 0 if not self.total else (self.page - 1) * self.size + 1

    @property
    def last(self) -> int:
        return min(self.total, self.page * self.size)


# Postgres type name -> the Python type a query-string value is converted to.
_PY_TYPES: dict[str, type] = {
    "int2": int, "int4": int, "int8": int, "bool": bool,
    "float4": float, "float8": float, "numeric": float,
    "timestamp": datetime, "timestamptz": datetime, "date": date,
}


@dataclass(frozen=True)
class Shape:
    """The columns a grid's query returns, and the Python type of each."""

    names: tuple[str, ...]
    types: dict[str, type | None]


_SHAPES: dict[str, Shape] = {}


def shape(spec: GridSpec, db: Db) -> Shape:
    """Asked of Postgres once per query: `SELECT * FROM (query) AS g LIMIT 0`."""
    key = spec.query.key
    if key not in _SHAPES:
        probe = text(f"SELECT * FROM ({spec.query.sql}) AS g LIMIT 0")
        description = db.conn.execute(probe, {"user_id": None}).cursor.description
        info = {d.name: pg_types.get(d.type_code) for d in description}
        _SHAPES[key] = Shape(names=tuple(info),
                             types={n: _PY_TYPES.get(t.name) if t else None for n, t in info.items()})
    return _SHAPES[key]


def coerce(py: type | None, value):
    """Convert a query-string value to the column's Python type. Raises ValueError."""
    if value is None or py is None:
        return value
    if py is bool:
        return str(value).lower() in ("1", "true", "yes", "on")
    if py in (datetime, date):
        return py.fromisoformat(str(value))
    return py(value)


def _coerce_all(py: type | None, values: list) -> list:
    """Values converted to the column's type; values that do not convert are dropped."""
    out = []
    for v in values:
        try:
            out.append(coerce(py, v))
        except (ValueError, TypeError):
            continue
    return out


class _Wrapped:
    """The named query as subquery `g`, with its column types."""

    def __init__(self, spec: GridSpec, db: Db):
        self.shape = shape(spec, db)
        self.sq = (spec.query.statement.columns(*(column(n) for n in self.shape.names))
                   .subquery("g"))
        self.c = self.sq.c

    def match(self, key: str, values: list) -> ColumnElement:
        values = _coerce_all(self.shape.types.get(key), values)
        col = self.c[key]
        if not values:
            return false()
        return col == values[0] if len(values) == 1 else col.in_(values)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def filtered(spec: GridSpec, db: Db, user, gq: GridQuery):
    """The spec query narrowed by fixed filters, view, filters and search, as (select, wrapped)."""
    g = _Wrapped(spec, db)
    conds = []
    for key, values in gq.fixed.items():
        if key not in g.c:
            raise ValueError(f"Grid {spec.key!r} has no column {key!r} to fix")
        conds.append(g.match(key, values))
    view = spec.view(gq.view)
    if view:
        for key, val in view.where.items():
            val = user.id if val == "$me" else val
            conds.append(g.match(key, val if isinstance(val, list) else [val]))
    for key, values in gq.filters.items():
        conds.append(g.match(key, values))
    for term in gq.q.split():
        pattern = f"%{_escape_like(term)}%"
        conds.append(or_(*(
            cast(g.c[k], String).ilike(pattern, escape="\\") for k in spec.search)))
    stmt = select(g.sq)
    if conds:
        stmt = stmt.where(and_(*conds))
    return stmt, g


def _ordered(stmt, g: _Wrapped, spec: GridSpec, gq: GridQuery):
    sort = gq.effective_sort(spec)
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    if key not in g.c:
        key, desc = "id", True
    col = g.c[key]
    stmt = stmt.order_by(col.desc() if desc else col.asc())
    if key != "id":
        stmt = stmt.order_by(g.c.id.desc() if desc else g.c.id.asc())
    return stmt


class GridTimeout(Exception):
    """A grid query ran longer than LATTICE_GRID_QUERY_TIMEOUT_SECONDS and was cancelled."""

    message = "This list took too long to load. Narrow the search or filters and try again."


@contextmanager
def _time_limit(db: Db) -> Iterator[None]:
    """Run grid reads in a savepoint with Postgres's statement_timeout set to the limit.

    Grid reads change nothing, so the savepoint is always rolled back: that also puts
    statement_timeout back. A cancelled query leaves the request's transaction usable.
    """
    if db.conn.connection.driver_connection.autocommit:
        yield                                   # no transaction (the tests' Db): no limit
        return
    savepoint = db.conn.begin_nested()
    try:
        db.conn.execute(text("SELECT set_config('statement_timeout', :ms, true)"),
                        {"ms": str(int(settings.grid_query_timeout_seconds * 1000))})
        yield
    except DBAPIError as exc:
        if isinstance(exc.orig, QueryCanceled):
            raise GridTimeout(GridTimeout.message) from exc
        raise
    finally:
        savepoint.rollback()


def read(db: Db, stmt, user) -> list[dict]:
    """Run a statement built on a grid query, within the grid time limit."""
    with _time_limit(db):
        return [dict(r) for r in db.conn.execute(stmt, {"user_id": user.id}).mappings()]


def _count(db: Db, stmt, user) -> int:
    counted = select(func.count()).select_from(stmt.subquery())
    with _time_limit(db):
        return db.conn.execute(counted, {"user_id": user.id}).scalar_one()


def count(spec: GridSpec, db: Db, user, gq: GridQuery) -> int:
    """Rows matching the grid state, through the spec query (so it respects row scoping)."""
    return _count(db, filtered(spec, db, user, gq)[0], user)


def fetch_page(spec: GridSpec, db: Db, user, gq: GridQuery) -> GridPage:
    stmt, g = filtered(spec, db, user, gq)
    page = GridPage(rows=[], total=_count(db, stmt, user), page=gq.page, size=gq.size)
    page.page = gq.page = min(gq.page, page.pages)
    stmt = _ordered(stmt, g, spec, gq).limit(gq.size).offset((gq.page - 1) * gq.size)
    page.rows = read(db, stmt, user)
    return page


def fetch_all(spec: GridSpec, db: Db, user, gq: GridQuery, limit: int) -> list[dict]:
    stmt, g = filtered(spec, db, user, gq)
    return read(db, _ordered(stmt, g, spec, gq).limit(limit), user)


def fetch_by_ids(spec: GridSpec, db: Db, user, ids: list) -> list[dict]:
    """Rows for `ids` that the spec query returns for this user. Unknown ids are dropped."""
    g = _Wrapped(spec, db)
    ids = _coerce_all(g.shape.types.get("id"), ids)
    if not ids:
        return []
    return read(db, select(g.sq).where(g.c.id.in_(ids)), user)
