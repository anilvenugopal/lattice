"""The shared Postgres engine, one transaction per request, and `Db`, the only way to run SQL.

One engine (SQLAlchemy Core over psycopg 3, with a connection pool) is created on
first use from LATTICE_DATABASE_URL. Lattice, every app, the migration runner, the
`lattice` command and background tasks all use it; nothing else creates engines.

A route gets a `Db` with `db: Db = Depends(get_db)`. The request runs in one
transaction: committed when the route returns, rolled back when it raises. Routes
never commit. Code outside a request opens its own: `with transaction() as db:`.

`Db` runs named queries (lattice/kernel/sql.py) and nothing else:

    db.all(SQL.users.list_active)                 -> list of dicts
    db.first(SQL.users.by_email, email=email)     -> dict, or None
    db.one(SQL.users.by_id, id=user_id)           -> dict, or NotFound (a 404 in a route)
    db.value(SQL.users.count)                     -> one value
    db.run(SQL.users.rename, id=1, name="Ann")    -> number of rows changed

Values are bound, never pasted into the SQL. A list becomes a Postgres array
(`WHERE id = ANY(:ids)`); a dict becomes JSONB.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from psycopg.types.json import Jsonb
from sqlalchemy import Connection, Engine, create_engine
from starlette.requests import Request

from lattice.kernel.config import settings
from lattice.kernel.sql import Query

_engine: Engine | None = None


def engine() -> Engine:
    """The shared engine, created on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def configure(url: str) -> None:
    """Point Lattice at another database (tests). Closes the old engine's connections."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(url, pool_pre_ping=True)


class NotFound(LookupError):
    """`Db.one` found no row. Routes turn it into a 404."""


def _bind(values: dict[str, Any]) -> dict[str, Any]:
    return {k: Jsonb(v) if isinstance(v, dict) else v for k, v in values.items()}


class Db:
    """Runs named queries on one connection, inside its transaction."""

    def __init__(self, conn: Connection):
        self.conn = conn
        self.after_commit: list[Callable[[], None]] = []   # run once the transaction commits

    def publish(self, type: str, subject: str = "", data: dict | None = None) -> None:
        """Announce an event (a CloudEvent, ADR 0011). Subscribers receive it after this
        transaction commits; if it rolls back, nobody does. `type` is "{app}.{event}" and
        must be declared in that app's manifest `publishes`."""
        from lattice.kernel import events  # events imports this module
        events.publish(self, type, subject, data)

    def _execute(self, query: Query, values: dict[str, Any]):
        if not isinstance(query, Query):
            raise TypeError("Db runs named queries from a sql/ folder, not SQL text")
        return self.conn.execute(query.statement, _bind(values))

    def all(self, query: Query, **values) -> list[dict]:
        return [dict(r) for r in self._execute(query, values).mappings()]

    def first(self, query: Query, **values) -> dict | None:
        row = self._execute(query, values).mappings().first()
        return dict(row) if row is not None else None

    def one(self, query: Query, **values) -> dict:
        row = self.first(query, **values)
        if row is None:
            raise NotFound(query.key)
        return row

    def value(self, query: Query, **values) -> Any:
        return self._execute(query, values).scalar()

    def run(self, query: Query, **values) -> int:
        return self._execute(query, values).rowcount


@contextmanager
def transaction() -> Iterator[Db]:
    """A `Db` in its own transaction: committed on success, rolled back on an exception.
    Work queued in `db.after_commit` (event delivery) runs once the commit succeeds."""
    with engine().begin() as conn:
        db = Db(conn)
        yield db
    for callback in db.after_commit:
        callback()


def get_db(request: Request) -> Iterator[Db]:
    """Route dependency: the request's `Db`, in one transaction for the whole request.
    Also on `request.state.db`, for template helpers such as `ref()`."""
    with transaction() as db:
        request.state.db = db
        yield db
