# 0008. Grid rows come from data sources with keyset paging

Status: Accepted in part (20 October 2026): keyset paging for SQL grids, built. Data
sources (async and merged) remain proposed until an app needs one.

## Context

The grid reads rows only from a SQLAlchemy query, with offset paging, in sync
code. Taskline's read API is async and returns dataclasses. The taskline Ops
console must list runs from several databases as one list. Incidents may read
from systems outside Lattice.

## Decision

- A grid takes a `GridSource` with `count`, `page(state, cursor)` and `by_ids`.
  `by_ids` remains the access boundary for actions, panels and export.
- Implementations:
  - `SqlSource(query)`, today's behaviour and the default;
  - an async source wrapping an async API;
  - a merged source that combines several sources, sorted by one key.
- Paging is keyset: a cursor on the sort key and id, not an offset. A merged
  source pages by merging the sources' cursors.
- Search, filters, views, sort, actions, export and Ctrl+J work the same for every
  source.

## Consequences

- Every list screen stays on the standard grid, whatever the data comes from.
- "Page N of M" is replaced by "next and previous" for sources that cannot count
  cheaply. SQL sources keep the total count.
- `GridSpec(query=…)` keeps working as a shorthand for `SqlSource(query)`.

## Rejected

- **A separate list component for non-SQL data.** It would duplicate the grid.
- **Offset paging for merged sources.** Offsets cannot be combined across databases.

## Keyset paging, as built (20 October 2026)

Taskline UI lists runs from views of a million rows, where offset paging cost about 80
microseconds per skipped row (442 ms at page 100, Taskline's measurement). The grid now
pages by keyset; data sources wait for a second, non-SQL source.

- **Next and Previous carry a cursor**: the boundary row's sort value and id, as an
  opaque token in the address (`after=` or `before=`). `page=` only labels the page;
  a page number without a cursor (an old link) is read by offset.
- **Index-friendly conditions**: a row comparison, `(sort, id) > (value, id)`, which an
  index on `(sort, id)` serves in order; nulls (last ascending, first descending, as
  Postgres orders them) are a second condition read only if the first runs out.
- **The count stays**: "Page N of M" and "1–50 of 240" are unchanged.
- **Measured** on a million rows sorted by time (each including the 21 ms count): page
  2, 23 ms; page 19,999, 24 ms by keyset against 77 ms by offset. On views that join
  (Taskline's), offset grows far faster and keyset stays flat.
- `tests/test_grid_keyset.py` walks every page forward and back for ten sort orders with
  ties and nulls, and checks the rows match offset paging exactly.
