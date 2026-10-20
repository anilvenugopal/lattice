"""Turns a GridSpec plus request parameters into SQL and rows.

`GridSpec.query` is a named query (a `.sql` file). The engine wraps it as a
subquery `g` and adds the view, filters, search, sort and paging around it:

    SELECT g.* FROM (<the named query>) AS g WHERE … ORDER BY … LIMIT … OFFSET …

This module and the migration runner are the only code in Lattice that builds SQL.
Column names come from the query itself (asked of Postgres once per query), and
values are always bound. The query may use `:user_id`, the signed-in user, to
scope rows, and the GridSpec's own `params` (fixed values such as a document kind).

Every read and every action goes through the query, so it is the grid's access
boundary: a row the query does not return cannot be shown, exported or acted on.
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from math import ceil

from psycopg.errors import QueryCanceled
from psycopg.postgres import types as pg_types
from sqlalchemy import (
    ColumnElement,
    Date,
    String,
    and_,
    bindparam,
    cast,
    column,
    false,
    func,
    or_,
    select,
    text,
    tuple_,
)
from sqlalchemy.exc import DBAPIError

from lattice.components.grid.spec import GridSpec
from lattice.kernel.config import settings
from lattice.kernel.database import Db
from lattice.kernel.services import preferences

PAGE_SIZES = preferences.PAGE_SIZES
DEFAULT_PAGE_SIZE = preferences.DEFAULTS["page_size"]
MAX_BULK = 10_000
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
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
    shape: str = ""                 # a drawn GeoJSON polygon (GridSpec.spatial grids)
    near: str = ""                  # "lon,lat,metres": rows within that distance of a point
    near_label: str = ""            # what the point is ("Lake Charles, LA"), for its chip
    # Keyset paging (ADR 0008): the page after or before a boundary row, as a cursor token.
    # Without one, page N is read by offset (page 1, and old links).
    after: str = ""
    before: str = ""

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
        shape = params.get("shape", "") if spec.spatial else ""
        near = params.get("near", "") if spec.spatial else ""
        return cls(
            shape=shape,
            near=near,
            near_label=(params.get("near_label", "") if near else "")[:120],
            q=(params.get("q") or "").strip(),
            sort=params.get("sort", ""),
            page=max(1, as_int("page", 1)),
            after=params.get("after", "")[:512],
            before="" if params.get("after") else params.get("before", "")[:512],
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
    next: str = ""                  # cursor for the page after this one
    previous: str = ""              # cursor for the page before it

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
    "timestamp": datetime, "timestamptz": datetime, "date": date, "uuid": uuid.UUID,
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
        description = db.conn.execute(probe, {"user_id": None, **spec.params}).cursor.description
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
    if py is uuid.UUID:
        return uuid.UUID(str(value))
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
        col = self.c[key]
        py = self.shape.types.get(key)
        if py is datetime and values and all(_DAY.fullmatch(str(v)) for v in values):
            days = _coerce_all(date, values)            # a day matches the whole day
            return cast(col, Date).in_(days) if days else false()
        values = _coerce_all(py, values)
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
    if gq.shape:
        lon, lat = spec.spatial
        point = func.ST_SetSRID(func.ST_MakePoint(g.c[lon], g.c[lat]), 4326)
        area = func.ST_SetSRID(func.ST_GeomFromGeoJSON(bindparam("shape", check_shape(gq.shape))),
                               4326)
        conds.append(func.ST_Intersects(point, area))
    if gq.near:
        lon, lat = spec.spatial
        x, y, metres = check_near(gq.near)
        here = func.ST_SetSRID(func.ST_MakePoint(g.c[lon], g.c[lat]), 4326)
        centre = func.ST_SetSRID(func.ST_MakePoint(x, y), 4326)
        conds.append(func.ST_DWithin(func.geography(here), func.geography(centre), metres))
    for term in gq.q.split():
        pattern = f"%{_escape_like(term)}%"
        conds.append(or_(*(
            cast(g.c[k], String).ilike(pattern, escape="\\") for k in spec.search)))
    stmt = select(g.sq)
    if conds:
        stmt = stmt.where(and_(*conds))
    return stmt, g


MAX_SHAPE_POINTS = 2000


def check_shape(shape: str) -> str:
    """A drawn shape, validated: a GeoJSON Polygon or MultiPolygon of at most 2,000 points."""
    try:
        geometry = json.loads(shape)
        kind = geometry["type"]
        points = (sum(len(r) for r in geometry["coordinates"]) if kind == "Polygon" else
                  sum(len(r) for p in geometry["coordinates"] for r in p))
        if kind not in ("Polygon", "MultiPolygon") or points > MAX_SHAPE_POINTS:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError("The drawn shape must be a polygon of at most 2,000 points") from None
    return json.dumps(geometry)


MAX_NEAR_METRES = 500_000


def check_near(near: str) -> tuple[float, float, float]:
    """A point and radius, validated: "lon,lat,metres" with a radius up to 500 km."""
    try:
        x, y, metres = (float(v) for v in near.split(","))
        if not (-180 <= x <= 180 and -90 <= y <= 90 and 0 < metres <= MAX_NEAR_METRES):
            raise ValueError
    except ValueError:
        raise ValueError("near must be longitude,latitude,metres with a radius up to 500 km") from None
    return x, y, metres


def _sort_key(g: _Wrapped, spec: GridSpec, gq: GridQuery) -> tuple[str, bool]:
    """The sort column and whether it ascends; an unknown column sorts by id, newest first."""
    sort = gq.effective_sort(spec)
    key = sort.lstrip("-")
    return (key, not sort.startswith("-")) if key in g.c else ("id", False)


def _ordered(stmt, g: _Wrapped, spec: GridSpec, gq: GridQuery, reverse: bool = False):
    """Sort by the grid's sort column, then id. Nulls go last ascending and first
    descending (Postgres's own default), which keyset paging relies on."""
    key, ascending = _sort_key(g, spec, gq)
    ascending ^= reverse
    for col in ([g.c[key], g.c.id] if key != "id" else [g.c.id]):
        stmt = stmt.order_by(col.asc().nulls_last() if ascending else col.desc().nulls_first())
    return stmt


def cursor(row: dict, key: str) -> str:
    """A boundary row as an opaque token: its sort value and id."""
    raw = json.dumps([row.get(key), row["id"]], default=str, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _uncursor(token: str, g: _Wrapped, key: str) -> tuple:
    try:
        value, row_id = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        if value is not None:
            py = g.shape.types.get(key)
            value = Decimal(str(value)) if py is float else coerce(py, value)
        return value, coerce(g.shape.types.get("id"), row_id)
    except (ValueError, TypeError, ArithmeticError):
        raise ValueError("The page link is out of date: go back to the first page") from None


def _beyond(g: _Wrapped, key: str, ascending: bool, value, row_id) -> list:
    """Conditions for the rows after the boundary (value, id) in the order (key, id), in
    the order they come: nulls last ascending, first descending. Each is a row comparison
    or a null test, so an index on (key, id) serves it; they are read in turn."""
    if key == "id":
        return [g.c.id > row_id if ascending else g.c.id < row_id]
    col = g.c[key]
    pair = tuple_(col, g.c.id)
    if ascending:
        return ([pair > tuple_(value, row_id), col.is_(None)] if value is not None
                else [and_(col.is_(None), g.c.id > row_id)])
    return ([pair < tuple_(value, row_id)] if value is not None
            else [and_(col.is_(None), g.c.id < row_id), col.is_not(None)])


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


def binds(spec: GridSpec, user) -> dict:
    """The values a grid's query is run with: the user and the spec's params."""
    return {"user_id": user.id, **spec.params}


def read(db: Db, stmt, values: dict) -> list[dict]:
    """Run a statement built on a grid query, within the grid time limit."""
    with _time_limit(db):
        return [dict(r) for r in db.conn.execute(stmt, values).mappings()]


def _count(db: Db, stmt, values: dict) -> int:
    counted = select(func.count()).select_from(stmt.subquery())
    with _time_limit(db):
        return db.conn.execute(counted, values).scalar_one()


def count(spec: GridSpec, db: Db, user, gq: GridQuery) -> int:
    """Rows matching the grid state, through the spec query (so it respects row scoping)."""
    return _count(db, filtered(spec, db, user, gq)[0], binds(spec, user))


def fetch_page(spec: GridSpec, db: Db, user, gq: GridQuery) -> GridPage:
    """One page of rows. With a cursor, the rows past it (keyset: as fast at page 1,000 as
    at page 1); without, page N by offset."""
    stmt, g = filtered(spec, db, user, gq)
    values = binds(spec, user)
    page = GridPage(rows=[], total=_count(db, stmt, values), page=gq.page, size=gq.size)
    page.page = gq.page = min(gq.page, page.pages)
    key, ascending = _sort_key(g, spec, gq)
    token = gq.after or gq.before
    if token and page.page > 1:
        forward = bool(gq.after)
        value, row_id = _uncursor(token, g, key)
        for cond in _beyond(g, key, ascending == forward, value, row_id):
            wanted = gq.size - len(page.rows)
            if wanted <= 0:
                break
            ordered = _ordered(stmt.where(cond), g, spec, gq, reverse=not forward)
            page.rows += read(db, ordered.limit(wanted), values)
        if not forward:
            page.rows.reverse()
    if not page.rows:
        offset = (page.page - 1) * gq.size
        page.rows = read(db, _ordered(stmt, g, spec, gq).limit(gq.size).offset(offset), values)
    if page.rows:
        page.next = cursor(page.rows[-1], key) if page.page < page.pages else ""
        page.previous = cursor(page.rows[0], key) if page.page > 1 else ""
    return page


def fetch_all(spec: GridSpec, db: Db, user, gq: GridQuery, limit: int) -> list[dict]:
    stmt, g = filtered(spec, db, user, gq)
    return read(db, _ordered(stmt, g, spec, gq).limit(limit), binds(spec, user))


def fetch_by_ids(spec: GridSpec, db: Db, user, ids: list) -> list[dict]:
    """Rows for `ids` that the spec query returns for this user. Unknown ids are dropped."""
    g = _Wrapped(spec, db)
    ids = _coerce_all(g.shape.types.get("id"), ids)
    if not ids:
        return []
    return read(db, select(g.sq).where(g.c.id.in_(ids)), binds(spec, user))
