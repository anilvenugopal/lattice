"""geoengine's migrations: `sql/schema/*.sql`, applied once each, in name order, into schema
`geo`, recorded in `geo._schema_version`.

The same layout and version table Lattice's runner uses, so a Lattice host applies these
files for an app that uses geoengine (`AppManifest.library_schemas=[geoengine.SCHEMA]`),
and `migrate()` applies them anywhere else. Both stop at the same files.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text

SCHEMA = ("geo", Path(__file__).parent / "sql" / "schema")


def migrate(target: str | Engine | Connection) -> list[str]:
    """Apply pending migrations; returns the files applied. Needs rights to create PostGIS."""
    if isinstance(target, Connection):
        return _apply(target)
    engine = create_engine(target) if isinstance(target, str) else target
    with engine.begin() as conn:
        return _apply(conn)


def _apply(conn: Connection) -> list[str]:
    schema, folder = SCHEMA
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('geoengine.migrate'))"))
    conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    conn.exec_driver_sql(f'CREATE TABLE IF NOT EXISTS "{schema}"._schema_version ('
                         "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r[0] for r in conn.execute(text(f'SELECT version FROM "{schema}"._schema_version'))}
    applied = []
    for path in sorted(folder.glob("*.sql")):
        if path.stem in done:
            continue
        conn.connection.cursor().execute(path.read_text(encoding="utf-8"))
        conn.execute(text(f'INSERT INTO "{schema}"._schema_version (version) VALUES (:v)'),
                     {"v": path.stem})
        applied.append(path.name)
    return applied


def schema_version(target: Connection) -> str:
    """The last migration applied, e.g. "0001_geo"; "" before any."""
    row = target.execute(text('SELECT max(version) FROM geo._schema_version')).scalar()
    return row or ""
