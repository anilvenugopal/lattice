---
title: Grid performance
summary: What the database actually runs for a grid, what is cheap, what is expensive on large tables, and how to keep grids fast.
order: 25
keywords: performance speed slow database index query plan explain subquery count search large table scale
---

A grid sends your query to the database wrapped in one larger statement (see
[Where the rows come from](grids.md#where-the-rows-come-from)). This page
shows what the database does with it, so you can tell a fast grid from a slow
one before your tables grow.

## What the database runs

For every load of a grid page, and every change (search, filter, view, sort,
page), the grid runs two statements:

1. **The page:** your query wrapped as a subquery `g`, with the view, filters,
   search, sort and `LIMIT`/`OFFSET` added around it. At most one page of rows
   comes back.
2. **The total**, for "1–50 of 240": `SELECT count(*)` over the same filtered
   query.

Opening a side panel, running an action on selected rows, or opening a Ctrl+J
preview looks rows up by `id`.

Nothing is filtered in the browser, and nothing reads a whole table just
because of the wrapping.

## The wrapping costs nothing

Databases merge a simple subquery into the outer query before running it, then
use indexes as usual. SQLite calls it flattening, Postgres calls it subquery
pull-up, and SQL Server expands derived tables. Here is SQLite's plan for the
Work Queue on the Open view with a priority filter. The first statement is
what the grid sends; the second is the same request written by hand:

```sql
SELECT * FROM (SELECT … FROM work_item LEFT JOIN app_user …) AS g
WHERE g.status IN ('new', 'in_review') AND g.priority = 'high'
ORDER BY g.received_at DESC LIMIT 50
```

```sql
SELECT … FROM work_item LEFT JOIN app_user …
WHERE work_item.status IN ('new', 'in_review') AND work_item.priority = 'high'
ORDER BY work_item.received_at DESC LIMIT 50
```

Both get the same plan:

```text
SEARCH work_item USING INDEX ix_work_item_status (status=?)
SEARCH app_user USING INTEGER PRIMARY KEY (rowid=?) LEFT-JOIN
USE TEMP B-TREE FOR ORDER BY
```

`SEARCH … USING INDEX` means the database jumps to the matching rows. It reads
only the open items, and each owner by its key.

## What is cheap and what is not

| Operation | Cost on a large table | Why |
|---|---|---|
| A view or filter on an indexed column | Cheap | The index finds the rows |
| Opening a row (panel, Ctrl+J preview, an action on selected rows) | Cheap | Lookup by `id`, the primary key |
| Sorting by an indexed column | Cheap | Rows come out of the index in order |
| Sorting by a column without an index | Grows with the matching rows | They are sorted before the page is cut |
| The total count | Grows with the matching rows | Every matching row is counted |
| Search (`contains`) | **Expensive** without a view or filter to narrow first | `LIKE '%word%'` cannot use a normal index, so every row is checked |
| Deep pages (page 400) | Grows with the page number | `OFFSET 20000` skips 20,000 rows each time |
| A grouped or summary query (`GROUP BY` inside) | Grows with the rows grouped | The grouping finishes before the outer filters apply |
| "Select all N matching" and CSV export | Up to 10,000 / 50,000 rows | They are read in one go |
| A grid with `poll_seconds` | The page and count, again and again | Once per interval for every open browser |

At a few thousand rows none of this matters. At hundreds of thousands, the
bold row does, and the others start to.

## Keep grids fast

**Index what you filter, sort and join on.** A view on `status` needs an index
on `status`. A default sort on `received_at` benefits from one on
`received_at`. Joins on foreign keys need the key indexed. For a view that
always filters and sorts together, one index on both columns covers it:

```python
class Ticket(Base):
    __tablename__ = "helpdesk_ticket"
    __table_args__ = (Index("ix_ticket_status_opened", "status", "opened_at"),)
    status: Mapped[str] = mapped_column(String(16), index=True)
```

**Make the first view narrow.** The first view is what every visit loads.
"Open" or "Assigned to me" reads far fewer rows than "All". Put "All" last.

**Keep `search` short.** Each search column adds a `LIKE` to every row
checked. List the columns people actually search: a reference, a title, a
name. Not long text such as descriptions.

**Keep grouped queries small, or move them out of the grid query.** A
grouped subquery is computed in full, even to show one row. The demo's
Administration › Users does this with each user's roles. It is fine because
the roles table is small. For large tables:

- store the total on the row and update it when it changes; or
- show it only in the side panel, which runs for one row; or
- use a correlated subquery, which the database runs per row shown:

```python
open_tickets = (select(func.count()).where(Ticket.customer_id == Customer.id,
                                           Ticket.status == "open")
                .correlate(Customer).scalar_subquery().label("open_tickets"))
```

**Use `poll_seconds` only where rows change by themselves**, such as a jobs
list, and not below 5 seconds.

**Check the plan.** Before a grid goes live on a large table, run the
statement through `EXPLAIN` (`EXPLAIN QUERY PLAN` on SQLite, `EXPLAIN ANALYZE`
on Postgres). Look for full scans (`SCAN` on SQLite, `Seq Scan` on Postgres)
of big tables.

## Coming improvements

These are planned, and listed in
[Decisions and direction](../architecture/decisions.md):

| Problem | Planned fix | Step |
|---|---|---|
| Search on large tables | Trigram indexes on Postgres (`pg_trgm`), which make `contains` search use an index | 2 |
| Slow queries running unchecked | A statement time limit for grid queries | 2 |
| Deep pages | Keyset paging: the next page starts after the last row seen, so no rows are skipped | 5 |
| The count on large lists | An option to show an estimate, or "more than 10,000", instead of an exact count | 5 |
| Large exports | Streaming the CSV from the database, instead of reading 50,000 rows at once | 5 |
