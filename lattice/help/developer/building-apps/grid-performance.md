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
   search, sort and `LIMIT` added around it. **Next** and **Previous** start
   after the last (or before the first) row seen, a keyset cursor, so no rows are
   skipped however deep the page. At most one page of rows comes back.
2. **The total**, for "1–50 of 240": `SELECT count(*)` over the same filtered
   query.

Opening a side panel, running an action on selected rows, or opening a Ctrl+J
preview looks rows up by `id`.

Nothing is filtered in the browser, and nothing reads a whole table just
because of the wrapping.

## The wrapping costs nothing

Postgres merges a simple subquery into the outer query before running it ("subquery
pull-up"), then uses indexes as usual. These plans are from Postgres 17, on a copy
of the demo with 300,000 work items. The first statement is what the grid sends for
a search; the second is the same search written by hand:

```sql
SELECT * FROM (SELECT w.id, w.ref, w.title, … , u.display_name AS owner
               FROM demo.work_item w LEFT JOIN lattice.app_user u ON u.id = w.owner_id) AS g
WHERE g.ref ILIKE '%WI-0012345%' OR g.title ILIKE '%WI-0012345%'
ORDER BY g.received_at DESC LIMIT 50
```

```sql
SELECT w.id, w.ref, w.title FROM demo.work_item w
LEFT JOIN lattice.app_user u ON u.id = w.owner_id
WHERE w.ref ILIKE '%WI-0012345%' OR w.title ILIKE '%WI-0012345%'
ORDER BY w.received_at DESC LIMIT 50
```

Both use the same indexes (trigram indexes on `ref` and `title`, see below):

```text
Bitmap Heap Scan on work_item w
  Bitmap Index Scan on work_item_ref_trgm
  Bitmap Index Scan on work_item_title_trgm
Execution Time: 2.3 ms (grid)    1.8 ms (by hand)
```

The plan reads `work_item w` directly: there is no step for `g`. The small
difference is the users table, which the hand-written query does not select, so
Postgres skips it. Opening one row by id (a panel, a Ctrl+J preview) is a
primary-key lookup: 0.1 ms.

## What is cheap and what is not

| Operation | Cost on a large table | Why |
|---|---|---|
| A view or filter on an indexed column | Cheap | The index finds the rows |
| Opening a row (panel, Ctrl+J preview, an action on selected rows) | Cheap | Lookup by `id`, the primary key |
| Sorting by an indexed column | Cheap | Rows come out of the index in order |
| Sorting by a column without an index | Grows with the matching rows | They are sorted before the page is cut |
| The total count | Grows with the matching rows | Every matching row is counted |
| Search (`contains`) | **Expensive**, unless the searched columns have trigram indexes (below) | `ILIKE '%word%'` cannot use a normal index, so every row is checked: 100 ms on 300,000 rows |
| Deep pages (page 400) | Cheap when reached by Next or Previous | They start after a cursor (keyset); only an old link with a page number and no cursor skips rows with `OFFSET` |
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

```sql
-- in a migration, apps/helpdesk/lattice_helpdesk/sql/schema/000N_….sql
CREATE INDEX ticket_status ON helpdesk.ticket (status);
CREATE INDEX ticket_status_opened ON helpdesk.ticket (status, opened_at);
```

**Make the first view narrow.** The first view is what every visit loads.
"Open" or "Assigned to me" reads far fewer rows than "All". Put "All" last.

**Keep `search` short.** Each search column adds an `ILIKE` to every row
checked. List the columns people actually search: a reference, a title, a
name. Not long text such as descriptions.

**Index search on a large table that people search.** Not every large table
needs search; for one that does, add trigram indexes in a migration. They let
Postgres find `contains` matches without reading every row: on 300,000 rows, a
search for one reference went from 105 ms to 2 ms.

```sql
-- apps/helpdesk/lattice_helpdesk/sql/schema/0002_search_indexes.sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ticket_ref_trgm ON helpdesk.ticket USING gin (ref gin_trgm_ops);
CREATE INDEX ticket_subject_trgm ON helpdesk.ticket USING gin (subject gin_trgm_ops);
```

> [!IMPORTANT]
> The indexes are used only when **every** column in the grid's `search` is on
> the grid's own table and indexed. Searching one joined column (an owner's
> name from `lattice.app_user`) makes Postgres read every row again: 63 ms
> instead of 2 ms in the example above. On a large searchable table, search its
> own columns and give people a filter (such as Owner) for the joined ones.

`pg_trgm` is a standard Postgres extension. Managed services (RDS, Azure,
Cloud SQL) allow it; a locked-down server may need an administrator to run
`CREATE EXTENSION pg_trgm` once.

**Keep grouped queries small, or move them out of the grid query.** A
grouped subquery is computed in full, even to show one row. The demo's
Administration › Users does this with each user's roles. It is fine because
the roles table is small. For large tables:

- store the total on the row and update it when it changes; or
- show it only in the side panel, which runs for one row; or
- use a correlated subquery, which the database runs per row shown:

```sql
SELECT c.id, c.name,
       (SELECT count(*) FROM helpdesk.ticket t
        WHERE t.customer_id = c.id AND t.status = 'open') AS open_tickets
FROM helpdesk.customer c
```

**Use `poll_seconds` only where rows change by themselves**, such as a jobs
list, and not below 5 seconds.

**Check the plan.** Before a grid goes live on a large table, run its
statement through `EXPLAIN ANALYZE` and look for `Seq Scan` on a big table.

## The time limit

A grid query (the rows, the count, an export, Ctrl+J results) that runs longer
than `LATTICE_GRID_QUERY_TIMEOUT_SECONDS` (15 by default) is cancelled by
Postgres. The user sees "This list took too long to load. Narrow the search or
filters and try again." as a message, and nothing else in the request is
affected. A slow grid never holds a database connection for minutes.

## Coming improvements

These are planned, and listed in
[Decisions and direction](../architecture/decisions.md):

| Problem | Planned fix | Step |
|---|---|---|
| The count on large lists | An option to show an estimate, or "more than 10,000", instead of an exact count | 5 |
| Large exports | Streaming the CSV from the database, instead of reading 50,000 rows at once | 5 |
