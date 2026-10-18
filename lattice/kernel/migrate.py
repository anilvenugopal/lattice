"""Schema migrations: plain `.sql` files, applied in name order, once each.

Lattice and every app own one Postgres schema each (`lattice`, `demo`…) and keep
their migrations in `sql/schema/` (0001_lattice.sql, 0002_….sql). The schema's
`_schema_version` table records which files have run. `lattice migrate` applies
Lattice's files first, then each app's, all in one transaction: a failure leaves
the database unchanged. An advisory lock stops two runs at once.

A file that has run is never edited; a change is a new file.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text

from lattice.kernel.database import engine

_SCHEMA = re.compile(r"^[a-z][a-z0-9_]*$")
LATTICE_SCHEMA = Path(__file__).parents[1] / "sql" / "schema"


class MigrationError(Exception):
    """A schema name or migration file breaks a rule."""


def pending(folder: Path, done: set[str]) -> list[Path]:
    return [p for p in sorted(folder.glob("*.sql")) if p.stem not in done]


def sources_for(apps) -> list[tuple[str, Path]]:
    """Lattice's migrations, then each app's (`AppManifest.sql`), in the host's order."""
    return [("lattice", LATTICE_SCHEMA)] + [(a.key, a.sql / "schema") for a in apps if a.sql]


def migrate(sources: list[tuple[str, Path]]) -> list[str]:
    """Apply pending files. `sources` is (schema, folder) in order. Returns "schema/file" applied."""
    applied: list[str] = []
    with engine().begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('lattice.migrate'))"))
        for schema, folder in sources:
            if not _SCHEMA.match(schema):
                raise MigrationError(f"Schema name {schema!r} must be lower_case_with_underscores")
            if not folder.is_dir():
                raise MigrationError(f"Schema {schema!r}: no migrations folder {folder}")
            conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            conn.exec_driver_sql(
                f'CREATE TABLE IF NOT EXISTS "{schema}"._schema_version ('
                "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            done = {r[0] for r in conn.execute(text(f'SELECT version FROM "{schema}"._schema_version'))}
            for path in pending(folder, done):
                conn.exec_driver_sql(path.read_text(encoding="utf-8"))
                conn.execute(text(f'INSERT INTO "{schema}"._schema_version (version) VALUES (:v)'),
                             {"v": path.stem})
                applied.append(f"{schema}/{path.name}")
    return applied


def drop_schemas(sources: list[tuple[str, Path]]) -> None:
    """Drop every schema in `sources`, with all its tables and data. Development only."""
    with engine().begin() as conn:
        for schema, _folder in reversed(sources):
            if not _SCHEMA.match(schema):
                raise MigrationError(f"Schema name {schema!r} must be lower_case_with_underscores")
            conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def new_migration(folder: Path, description: str) -> Path:
    """Create the next numbered migration file in `folder`: 0002_add_tickets.sql."""
    slug = re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_")
    if not slug:
        raise MigrationError("Describe the change, e.g. \"add ticket table\"")
    numbers = [int(p.stem[:4]) for p in folder.glob("[0-9][0-9][0-9][0-9]_*.sql")]
    path = folder / f"{max(numbers, default=0) + 1:04d}_{slug}.sql"
    path.write_text(f"-- {description}\n\n", encoding="utf-8")
    return path
