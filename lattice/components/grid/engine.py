"""Turns a GridSpec plus request parameters into SQL and rows.

Every read and every action goes through `GridSpec.query`, so the query is the
grid's access boundary: a row the query does not return cannot be shown,
exported or acted on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import ceil

from sqlalchemy import ColumnElement, String, and_, cast, false, func, or_, select
from sqlalchemy.orm import Session

from lattice.components.grid.spec import GridSpec
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


def coerce(column: ColumnElement, value):
    """Convert a query-string value to the column's Python type. Raises ValueError."""
    if value is None:
        return None
    try:
        py = column.type.python_type
    except NotImplementedError:
        return value
    if py is bool:
        return str(value).lower() in ("1", "true", "yes", "on")
    if py is int:
        return int(value)
    if py is float:
        return float(value)
    if py is datetime:
        return datetime.fromisoformat(value)
    if py is date:
        return date.fromisoformat(value)
    return value


def _coerce_all(column, values: list) -> list:
    """Values converted to the column's type; values that do not convert are dropped."""
    out = []
    for v in values:
        try:
            out.append(coerce(column, v))
        except (ValueError, TypeError):
            continue
    return out


def _match(column, values: list) -> ColumnElement:
    values = _coerce_all(column, values)
    if not values:
        return false()
    return column == values[0] if len(values) == 1 else column.in_(values)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def filtered(spec: GridSpec, db: Session, user, gq: GridQuery):
    """The spec query narrowed by view, filters and search, as (select, subquery)."""
    sq = spec.query(db, user).subquery("g")
    conds = []
    view = spec.view(gq.view)
    if view:
        for key, val in view.where.items():
            val = user.id if val == "$me" else val
            conds.append(_match(sq.c[key], val if isinstance(val, list) else [val]))
    for key, values in gq.filters.items():
        conds.append(_match(sq.c[key], values))
    for term in gq.q.split():
        pattern = f"%{_escape_like(term)}%"
        conds.append(or_(*(
            cast(sq.c[k], String).ilike(pattern, escape="\\") for k in spec.search)))
    stmt = select(sq)
    if conds:
        stmt = stmt.where(and_(*conds))
    return stmt, sq


def _ordered(stmt, sq, spec: GridSpec, gq: GridQuery):
    sort = gq.effective_sort(spec)
    desc = sort.startswith("-")
    key = sort.lstrip("-")
    if key not in sq.c:
        key, desc = "id", True
    col = sq.c[key]
    stmt = stmt.order_by(col.desc() if desc else col.asc())
    if key != "id":
        stmt = stmt.order_by(sq.c.id.desc() if desc else sq.c.id.asc())
    return stmt


def _count(db: Session, stmt) -> int:
    return db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()


def count(spec: GridSpec, db: Session, user, gq: GridQuery) -> int:
    """Rows matching the grid state, through the spec query (so it respects row scoping)."""
    return _count(db, filtered(spec, db, user, gq)[0])


def fetch_page(spec: GridSpec, db: Session, user, gq: GridQuery) -> GridPage:
    stmt, sq = filtered(spec, db, user, gq)
    page = GridPage(rows=[], total=_count(db, stmt), page=gq.page, size=gq.size)
    page.page = gq.page = min(gq.page, page.pages)
    stmt = _ordered(stmt, sq, spec, gq).limit(gq.size).offset((gq.page - 1) * gq.size)
    page.rows = [dict(r) for r in db.execute(stmt).mappings()]
    return page


def fetch_all(spec: GridSpec, db: Session, user, gq: GridQuery, limit: int) -> list[dict]:
    stmt, sq = filtered(spec, db, user, gq)
    stmt = _ordered(stmt, sq, spec, gq).limit(limit)
    return [dict(r) for r in db.execute(stmt).mappings()]


def fetch_by_ids(spec: GridSpec, db: Session, user, ids: list) -> list[dict]:
    """Rows for `ids` that the spec query returns for this user. Unknown ids are dropped."""
    if not ids:
        return []
    sq = spec.query(db, user).subquery("g")
    ids = _coerce_all(sq.c.id, ids)
    if not ids:
        return []
    stmt = select(sq).where(sq.c.id.in_(ids))
    return [dict(r) for r in db.execute(stmt).mappings()]
