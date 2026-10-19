---
title: Data and audit
summary: Tables and migrations, named SQL queries, running them with Db, transactions, the audit log, example data and background work.
order: 60
keywords: database postgres sql query named queries migration schema Db transaction audit history timeline seed background
---

Lattice uses Postgres and plain SQL, with no ORM:

- **Tables** are created by migration files: plain `.sql`, applied in order.
- **Queries** are named, in `.sql` files, one file per area. Python code refers
  to a query by name and never contains SQL.
- **Running them** goes through `Db`, with one transaction per request.

What runs is always exactly what is in the files.

## The database

One Postgres database holds everything. Each app has its own **schema** in it,
named after the app's key:

| Schema | Holds |
|---|---|
| `lattice` | Lattice's tables: users, roles, sessions, preferences, the audit log |
| `showcase` | The showcase app's tables |
| `helpdesk`, … | Each app's own tables |

An app may read Lattice's tables, for example to join `lattice.app_user` for a
person's name, and may refer to a user by `lattice.app_user.id`. It never reads
or writes another app's schema.

The connection is `LATTICE_DATABASE_URL`. Lattice creates one connection pool
when it starts, and everything shares it.

## Tables and migrations

An app keeps its migrations in `sql/schema/` and declares the folder in its
manifest with `sql=HERE / "sql"`:

```text
lattice_helpdesk/sql/
  schema/
    0001_helpdesk.sql        the first tables
    0002_ticket_priority.sql a later change
  tickets.sql                named queries (below)
```

```sql
-- lattice_helpdesk/sql/schema/0001_helpdesk.sql
-- The helpdesk's tables. Lattice creates the helpdesk schema before this runs.

CREATE TABLE helpdesk.ticket (
  id          bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ref         varchar(32)  NOT NULL UNIQUE,
  subject     varchar(255) NOT NULL,
  status      varchar(16)  NOT NULL DEFAULT 'new',
  assignee_id bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  opened_at   timestamp    NOT NULL DEFAULT lattice.utc_now()
);
CREATE INDEX ticket_status ON helpdesk.ticket (status);
```

`lattice migrate` (`make migrate`) applies, in order:

1. Lattice's files;
2. each app's files, in the host's app order.

Each schema has a `_schema_version` table recording which files have run, so
each file runs once. All pending files run in one transaction: if one fails,
nothing changes.

| Command | Does |
|---|---|
| `make migration schema=helpdesk m="add ticket priority"` | Creates the next numbered file, `0002_add_ticket_priority.sql`, for you to fill in |
| `make migrate` | Applies every pending file |
| `make reset` | Drops Lattice's and the apps' schemas, then migrates and seeds again. Development only |

Rules:

- **Timestamps:** naive UTC, from the database clock: `timestamp` columns with
  `DEFAULT lattice.utc_now()`. `time_tag` shows them in the user's time zone.
- **Never edit a migration that has run** on a shared database. Write a new file.
- **Lookup rows go with their table.** Seed rows such as roles or ticket kinds in
  the same file that creates the table, so every database has them.
- **References between apps.** Never add a foreign key to another app's table;
  refer to its records by id or reference.

## Named queries

Queries live in `sql/<area>.sql`, one file per area of the app:

```sql
-- lattice_helpdesk/sql/tickets.sql
-- Tickets: customer requests from opening to close.

-- name: grid
-- Every ticket with its assignee's name. The grid adds search, filters, sort and paging.
SELECT t.id, t.ref, t.subject, t.status, t.assignee_id,
       u.display_name AS assignee, t.opened_at
FROM helpdesk.ticket t
LEFT JOIN lattice.app_user u ON u.id = t.assignee_id;

-- name: by_id
-- One ticket.
SELECT id, ref, subject, status, assignee_id, opened_at FROM helpdesk.ticket WHERE id = :id;

-- name: close
-- Close tickets.
UPDATE helpdesk.ticket SET status = 'closed' WHERE id = ANY(:ids);
```

The rules, checked when the files load:

- **Names:** every query starts with `-- name: <name>`, unique in its file, in
  `lower_case_with_underscores`.
- **Comments:** the next line is a `--` comment saying what the query does.
- **Placeholders:** values are written `:name` and bound separately, never
  pasted into the SQL.
- **Casts:** a cast on a placeholder is written `CAST(:x AS date)`. `:x::date`
  is not bound, and the file is refused.

Load an area's queries once, at the top of the module:

```python
from pathlib import Path

from lattice.api import sql_queries

SQL = sql_queries(Path(__file__).parent / "sql").tickets    # SQL.grid, SQL.by_id, SQL.close
```

Every statement sent to Postgres starts with a comment naming its query:
`/* lattice_helpdesk/tickets.close */ UPDATE …`. A slow query in the Postgres
logs points straight at its file.

## Running queries: Db

A route gets the request's `Db` from `Depends(get_db)`. `Db` runs named
queries, and nothing else:

| Call | Returns |
|---|---|
| `db.all(SQL.grid)` | Every row, as a list of dicts |
| `db.first(SQL.by_email, email=e)` | The first row as a dict, or `None` |
| `db.one(SQL.by_id, id=7)` | One row as a dict, or `NotFound`, which a route turns into a 404 page |
| `db.value(SQL.count)` | One value, such as a count or a new row's id from `RETURNING id` |
| `db.run(SQL.close, ids=[1, 2])` | The number of rows changed, for `INSERT`, `UPDATE` and `DELETE` |

Values are keyword arguments:
- a Python list becomes a Postgres array, used with `= ANY(:ids)`;
- a dict becomes JSONB;
- `None` becomes `NULL`.

```python
@router.get("/tickets/{ticket_id}")
def detail(ticket_id: int, request: Request, db: Db = Depends(get_db)):
    ticket = db.one(SQL.by_id, id=ticket_id)          # 404 if there is none
    return render_page(request, "helpdesk/ticket.html", "tickets.detail", ticket=ticket,
                       crumb=ticket["ref"])
```

Rows are plain dicts. Templates read them as `ticket.ref`, as they would an
object.

### One transaction per request

A request runs in one transaction:

- **Saved** when the route returns.
- **Rolled back** when it raises. A request that fails halfway leaves nothing behind.
- **Never committed by routes.** Grid action handlers run in the same transaction.

Code outside a request opens its own:

```python
from lattice.api import transaction

with transaction() as db:
    db.run(SQL.close_stale)
```

## The audit log

Every change a user makes is recorded in `lattice.audit_event`. Administrators
read it in **Administration › Audit log**, and record pages show it with the
`timeline` macro.

**Grid actions are audited for you.** The grid writes one event per row, with:

- the action `{grid key}.{action key}`;
- the target type set to the grid key, and the target id set to the row id;
- the input values of the dialog, if any.

**Every other write** calls `audit.record` in the same request:

```python
audit.record(db, user.id, "helpdesk.tickets.reopen", f"Reopened {ticket['ref']}",
             target_type="helpdesk.tickets", target_id=ticket["id"],
             detail={"reason": reason})
```

| Argument | Is |
|---|---|
| `actor_id` | The user who acted; `None` for the system |
| `action` | A dotted name, starting with the app key |
| `summary` | One line a person can read |
| `target_type`, `target_id` | The record. Use the grid key as the type, so grid actions and other writes share one history |
| `detail` | Optional JSON with the values that changed |

Events written in one request share their time. Never put passwords, tokens or
other secrets in `summary` or `detail`.

Show a record's history with:

```python
events = audit.history(db, "helpdesk.tickets", ticket_id, limit=20)
```

```jinja
{% call card("Activity") %}{{ timeline(events) }}{% endcall %}
```

`history` returns one line per bulk action, not one per row.

## Example data

`AppManifest.seed` is a function `(db)` that adds example rows for
development. `lattice seed` runs it once, after creating the development users,
in one transaction, and never in production:

```python
def seed(db: Db) -> None:
    people = [r["id"] for r in db.all(SQL.people)]
    rng = random.Random(7)                          # the same data for every developer
    for i in range(1, 51):
        db.run(SQL.add_ticket, ref=f"T-{i:04d}", subject=f"Example {i}",
               assignee_id=rng.choice(people))
```

The showcase's `seed.py` and `sql/seed.sql` are a full example.

## Background work

`AppManifest.background` is an async function. The host starts it with the
application and cancels it at shutdown. Use it for small periodic jobs in
development and demonstrations, such as the showcase's job simulator:

```python
async def background() -> None:
    def sweep():
        with transaction() as db:                   # its own transaction
            db.run(SQL.close_stale)

    while True:
        await asyncio.sleep(60)
        try:
            await run_in_threadpool(sweep)           # database work off the event loop
        except Exception:
            log.exception("sweep failed")             # keep the loop alive
```

It runs in every web process, with no retries and no record of runs. Real
background jobs will run on taskline (see
[Decisions and direction](../architecture/decisions.md)).

## What Lattice checks

These checks run in `make test` and `make lint`, for Lattice and every app:

| Check | Fails when |
|---|---|
| Loading the `.sql` files | A query has no name or comment, a name is used twice, or a placeholder is followed by `::` |
| Every query used | A named query no code uses (delete it) |
| Every name real | Code names a query that does not exist |
| Valid SQL | Postgres rejects a named query when asked to `EXPLAIN` it, for example a misspelt column |
| SQL only in files | A SQL statement is written as a string in Python |
| No ORM | Code imports `sqlalchemy.orm` |
| Apps through `lattice.api` | An app imports SQLAlchemy or psycopg directly |

Only two Lattice modules build SQL in code: the grid engine, which adds search,
filters, sort and paging around a grid's query, and the migration runner.
