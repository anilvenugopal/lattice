# 0001. Postgres only, with per-app database bindings

Status: Accepted

## Context

Lattice will host several apps. Some of them, such as taskline, already require
Postgres. Each app keeps its own data, and a host may put all apps in one
database or give some their own. Today Lattice uses SQLite by default with one
connection.

## Decision

- Postgres is the only supported database. SQLite is removed, including from tests.
- Each app declares named **bindings** (`default`, or one per instance). The host
  maps each binding to a URL in settings. An unmapped binding uses Lattice's own
  database.
- Each app owns one Postgres schema and keeps its Alembic version table in it.
  `lattice migrate` migrates every app against its binding. An app whose library
  migrates itself (taskline) declares that instead.
- Apps refer to each other's records by reference (`kind:id`), never by foreign key.
- A binding provides a sync and an async SQLAlchemy engine from the same URL (psycopg 3).

## Consequences

- Shared or separate databases is a configuration choice, not a code change.
- There are no transactions across bindings. Audit records and events are written
  after the app's own commit. An event that must not be lost needs an outbox table
  in the publishing app.
- No joins across apps. Lists that combine apps go through references or a merged
  grid source ([0008](0008-grid-data-sources.md)).
- Development needs a Postgres container. Tests create a database per test, as
  taskline's tests do.

## Rejected

- **Keeping SQLite for development.** Per-app schemas, JSONB and taskline do not work on it.
- **One shared database with table prefixes.** It rules out separate databases per app.

## Note, 18 October 2026: what step 2 built

Postgres only, a schema per app and per-app migrations are built. Narrowed in
the step 2 decisions (see the developer guide, *Architecture › Decisions and
direction*):

- **One database for now.** Bindings to separate databases are not built; they
  come when an app needs one (the taskline Ops console).
- **Plain SQL, no ORM.** Migrations are plain `.sql` files run by a small runner,
  not Alembic.
- **Sync only until step 6.** The async engine comes with the taskline app.
