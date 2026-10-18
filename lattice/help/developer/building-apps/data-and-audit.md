---
title: Data and audit
summary: Models, migrations, timestamps, the audit log, example data and background work.
order: 60
keywords: database model sqlalchemy migration alembic revision audit history timeline seed background task timestamp utc
---

## Models

An app's tables live in its `models.py`. They extend `Base` from
`lattice.api`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from lattice.api import Base, utcnow


class Ticket(Base):
    """A customer request, from opening to close."""

    __tablename__ = "helpdesk_ticket"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(32), unique=True)
    subject: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

| Rule | Why |
|---|---|
| Choose table names no other app will use; prefixing with the app key (`helpdesk_ticket`) is the safe choice | All apps share one database today, so two tables with one name collide |
| Store timestamps as naive UTC, with `default=utcnow` | `time_tag` formats them in the user's time zone |
| Refer to people by `app_user.id` | Lattice owns the user table; apps may point at it |
| Never point a foreign key at another app's table | Apps will move to their own databases; refer to their records by id or reference instead |
| Use SQLAlchemy sessions and bind parameters only | No string-built SQL |

Routes get a session from `Depends(get_db)`. Background code opens its own
with `SessionLocal()`.

## Migrations

Until each app has its own migrations, every table is in one Alembic history
in `alembic/`, and `alembic/env.py` imports each app's models.

To change the schema:

1. Edit the models.
2. Generate a migration:

   ```bash
   make revision m="add helpdesk ticket table"
   ```

3. **Read the generated file** in `alembic/versions/`. Autogenerate misses
   some changes, such as a renamed column (it sees a drop and an add) or a
   changed server default. Fix anything it got wrong.
4. Apply it:

   ```bash
   make migrate
   ```

Rules:

- **Never edit a migration that has been merged.** Write a new one.
- **Seed lookup rows in the migration that creates their table**, such as
  roles or ticket kinds, so every database has them.
- **SQLite needs batch mode** for most `ALTER TABLE` changes. `env.py` turns
  it on (`render_as_batch=True`), so generated migrations already use
  `op.batch_alter_table`.

## The audit log

Every change a user makes is recorded in `audit_event`. Administrators read it
in **Administration › Audit log**, and record pages show it with the
`timeline` macro.

**Grid actions are audited for you.** The grid writes one event per row, with:

- the action `{grid key}.{action key}`;
- the target type set to the grid key, and the target id set to the row id;
- the input values of the dialog, if any.

**Every other write** calls `audit.record` before its commit:

```python
audit.record(db, user.id, "helpdesk.tickets.reopen", f"Reopened {ticket.ref}",
             target_type="helpdesk.tickets", target_id=ticket.id,
             detail={"reason": reason})
db.commit()
```

| Argument | Is |
|---|---|
| `actor_id` | The user who acted; `None` for the system |
| `action` | A dotted name, starting with the app key |
| `summary` | One line a person can read |
| `target_type`, `target_id` | The record. Use the grid key as the type, so grid actions and other writes share one history |
| `detail` | Optional JSON with the values that changed |

Never put passwords, tokens or other secrets in `summary` or `detail`.

Show a record's history with:

```python
events = audit.history(db, "helpdesk.tickets", ticket.id, limit=20)
```

```jinja
{% call card("Activity") %}{{ timeline(events) }}{% endcall %}
```

`history` returns one line per bulk action, not one per row.

## Example data

`AppManifest.seed` is a function `(db) -> None` that adds example rows for
development. `lattice seed` runs it once, after creating the development users,
and never in production:

```python
def seed(db) -> None:
    people = list(db.scalars(select(User).order_by(User.id)))
    db.add_all(Ticket(ref=f"T-{i:04d}", subject=f"Example {i}",
                      assignee_id=people[i % len(people)].id) for i in range(1, 51))
    db.commit()
```

Use a fixed random seed (`random.Random(7)`) so every developer sees the same data.

## Background work

`AppManifest.background` is an async function. The host starts it with the
application and cancels it at shutdown. Use it for small periodic jobs in
development and demos, such as the demo app's job simulator:

```python
async def background() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await run_in_threadpool(sweep_expired)     # sync database code off the event loop
        except Exception:
            log.exception("sweep failed")             # keep the loop alive
```

It runs in every web process, with no retries and no record of runs. Real
background jobs will run on taskline (see
[Decisions and direction](../architecture/decisions.md)).
