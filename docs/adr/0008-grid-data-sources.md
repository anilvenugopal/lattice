# 0008. Grid rows come from data sources with keyset paging

Status: Proposed

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
