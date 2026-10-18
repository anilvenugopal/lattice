# Step 2 plan: Postgres and plain SQL

Status: **draft for approval**. No code has been written.

## What step 2 delivers

- **Postgres only.** One database. Lattice's tables in schema `lattice`, each
  app's tables in its own schema (the demo's in `demo`). SQLite is removed.
- **Plain SQL, no ORM.**
  - Every SQL statement lives in a named query in a `.sql` file.
  - Code refers to queries by name.
  - Database access runs through SQLAlchemy Core, with psycopg 3 as the driver.
- **One shared engine.** Lattice creates it once. Lattice, every app, the
  migration runner, the `lattice` command and background tasks all use it.
- **One transaction per request.** It is committed when the route succeeds and
  rolled back when it fails. Routes never call `commit`.
- **SQL migrations.** Each package has `sql/schema/*.sql` files, applied in
  order, with a version table in its own schema, like taskline. Alembic is
  removed.
- **Grid performance on Postgres:**
  - trigram search indexes;
  - a time limit on grid queries;
  - query plans checked with `EXPLAIN ANALYZE`.
- **Docs and the tutorial** updated to the new way of writing apps.

The demo looks and behaves exactly as it does now.

## Decisions taken (in our discussion on 18 Oct 2026)

| Topic | Decision |
|---|---|
| Database | Postgres only; one database, one schema per app |
| ORM or SQL | Plain SQL in named files; no ORM |
| Library | SQLAlchemy Core (engine and `text()`), psycopg 3 as the driver |
| Placeholders | `:name`, as in strategiq and taskline |
| Query files | One file per area, with named queries |
| Transactions | One per request, committed automatically |
| Migrations | Plain `.sql` files and a small runner, like taskline |
| Existing data | None kept; migrations start fresh |
| Async | Not in step 2; added in step 6 when taskline needs it |

## How an app's code will look

```text
apps/demo/lattice_demo/sql/
  schema/0001_demo.sql      CREATE SCHEMA demo; CREATE TABLE demo.work_item …
  work_items.sql            named queries for the Work Queue
```

```sql
-- apps/demo/lattice_demo/sql/work_items.sql

-- name: grid
-- Every work item with its owner's name. The grid adds search, filters, sort and paging.
SELECT w.id, w.ref, w.title, w.account, w.status, w.priority, w.owner_id,
       u.display_name AS owner, w.amount, w.received_at, w.updated_at
FROM demo.work_item w
LEFT JOIN lattice.app_user u ON u.id = w.owner_id;

-- name: approve
-- Approve the given items.
UPDATE demo.work_item SET status = 'approved', updated_at = now()
WHERE id = ANY(:ids);
```

```python
from lattice.api import GridSpec, sql_queries

SQL = sql_queries(__file__)      # loads this package's sql/*.sql, checked at startup

def approve(ctx):
    ctx.db.run(SQL.work_items.approve, ids=ctx.ids)
    return f"Approved {ctx.count} item(s)."

GRID = GridSpec(key="demo.work_items", query=SQL.work_items.grid, …)

@router.get("/work/{item_id}")
def detail(item_id: int, request: Request, db=Depends(get_db)):
    item = db.one(SQL.work_items.by_id, id=item_id)     # a dict, or 404
    …
```

`db` offers four calls, with no other way to run SQL:

| Call | Returns |
|---|---|
| `db.all(query, **values)` | A list of rows as dicts |
| `db.one(query, **values)` | One row as a dict, or 404 if there is none |
| `db.value(query, **values)` | A single value, such as a count |
| `db.run(query, **values)` | Nothing; for `INSERT`, `UPDATE` and `DELETE` |

A grid query may use `:user_id` (the signed-in user) for row scoping, as the
Inbox does: `WHERE m.owner_id = :user_id`.

## The governance checks (automatic)

1. **Names.** Every query has a `-- name:` that is unique in its file, and a
   comment line saying what it does.
2. **Missing queries.** A query name used in code but missing from the files
   stops the host at startup, naming the file and query.
3. **Dead SQL.** A named query no code uses fails the tests.
4. **Valid SQL.** Every named query is checked with `EXPLAIN` against Postgres
   in the tests, so a wrong column or a typo fails with the file and name.
5. **SQL only in `sql/` folders.** A test fails on a SQL statement written as a
   string in Python.
6. **No ORM.** Lint fails on any import of `sqlalchemy.orm`. Apps may not
   import SQLAlchemy at all; they use `lattice.api`.
7. **Traceable queries.** Every statement sent carries its name as a comment
   (`/* demo:work_items.grid */`), so the Postgres logs show where a slow
   query comes from.

Only two Lattice modules build SQL in code: the grid engine (the wrapper
around a grid's query) and the migration runner.

## Stages

Work happens on a branch, `step-2`, with one commit per stage. The branch is
merged into `main` only when every stage is done, all tests pass, and you have
reviewed it. Stages 2 to 4 rewrite code that depends on each other, so the
full test suite passes again from the end of stage 4.

| # | Stage | Contents |
|---|---|---|
| 1 | **Foundations** | The shared engine; the SQL file loader and its startup checks; the migration runner; the `db` object with the four calls and one transaction per request; Lattice's schema file; `compose.yaml` with Postgres 17; test fixtures with one fresh database per test, cloned from a migrated template so tests stay fast |
| 2 | **Lattice's own code on SQL** | Sign-in, sessions, users, roles, audit, preferences; Administration, Account and Home; the `lattice` command. Lattice's named queries in `lattice/sql/` |
| 3 | **The grid on named queries** | The engine wraps a named query; actions, panels, export, tiles and Ctrl+J use `db`; the grid tests rewritten |
| 4 | **The demo app on SQL** | The `demo` schema; Work Queue, Jobs and Inbox queries; seed data; the demo's tests. **All tests pass from here** |
| 5 | **Remove the old way and add the checks** | Delete SQLite support, model classes, Alembic and the `alembic/` folder; add governance checks 3 to 7 |
| 6 | **Grid performance** | `pg_trgm` and trigram indexes on the demo's search columns; a statement time limit for grid queries (`LATTICE_GRID_QUERY_TIMEOUT_SECONDS`, default 15), with a clear message to the user when it is hit; the demo grids' `EXPLAIN ANALYZE` plans recorded on the Grid performance page |
| 7 | **Docs** | Every page that describes models, Alembic or SQLite: Getting started, Your first app (rebuilt and tested again end to end), Data and audit, Grids, Grid performance, Access control, Testing, Running Lattice, Architecture, Contributing; the Reference pages; AGENTS.md, the README, the add-grid-page skill; ARCHITECTURE.md and a note on ADR 0001 recording these decisions |

## What changes for you

- **Postgres must be running** for `make dev` and `make test`. On this
  machine `docker` is not reachable from WSL, but **podman 5.7 is installed
  and works**. `compose.yaml` will run with `podman compose up -d`. You start
  and stop the container; I will not.
- **New commands:**
  - `make db-up` and `make db-down` (you run them);
  - `make migrate` applies the SQL files;
  - `make reset` drops and rebuilds the database.

## Not in step 2

- **Async database access.** Comes in step 6, with taskline.
- **Separate databases per app.** You chose one database with a schema per
  app. ADR 0001's per-app database URLs are not built; a note on ADR 0001 will
  say so.
- **Sharing Lattice's engine with taskline.** Comes in step 6.

## Scale

This is the largest step so far:

- 36 files change;
- about 130 database calls are rewritten;
- 9 table classes become `CREATE TABLE` statements;
- the 200 tests stay, rewritten where they create rows.

## To approve

1. This plan as written, or with changes.
2. Postgres 17 on port **5435**, so it does not clash with strategiq's 5434 or
   a default 5432.
