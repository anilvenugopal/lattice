"""refdata's schema `ref`: migrations in `sql/schema/*.sql`, applied once each in name order
and recorded in `ref._schema_version` (the layout Lattice's runner uses), then the bundled
datasets loaded where missing.

A Lattice app installs it with the migration hook:
`AppManifest(libraries=[Library("refdata", ["ref"], refdata.migrate)])`.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection, Engine, create_engine, text

SCHEMA = "ref"
FOLDER = Path(__file__).parent / "sql" / "schema"


def migrate(target: str | Engine | Connection) -> list[str]:
    """Apply pending migrations and load missing datasets; returns what was done."""
    if isinstance(target, Connection):
        return _apply(target)
    engine = create_engine(target) if isinstance(target, str) else target
    with engine.begin() as conn:
        return _apply(conn)


def _apply(conn: Connection) -> list[str]:
    from refdata.places import load_places

    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('refdata.migrate'))"))
    conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    conn.exec_driver_sql(f'CREATE TABLE IF NOT EXISTS "{SCHEMA}"._schema_version ('
                         "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r[0] for r in conn.execute(text(f'SELECT version FROM "{SCHEMA}"._schema_version'))}
    applied = []
    for path in sorted(FOLDER.glob("*.sql")):
        if path.stem in done:
            continue
        conn.connection.cursor().execute(path.read_text(encoding="utf-8"))
        conn.execute(text(f'INSERT INTO "{SCHEMA}"._schema_version (version) VALUES (:v)'),
                     {"v": path.stem})
        applied.append(path.name)
    if added := load_places(conn):
        applied.append(f"places ({added})")
    return applied
