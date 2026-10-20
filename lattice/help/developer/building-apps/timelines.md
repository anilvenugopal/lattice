---
title: Timelines
summary: Bars on a time axis in lanes, from a grid's rows: progress through stages, who was busy when, runs over a window. Markers, a "now" line, zoom, and click to open.
order: 27
keywords: timeline gantt lanes bars segments markers now zoom window schedule workload duration
---

A timeline draws the rows of a grid as bars on a time axis, grouped in lanes
([ADR 0014](/help/lattice/developer/architecture/decisions)). Like a
[chart](charts.md) or a [map](maps.md), it reads the grid's query, so the
grid's access rules apply, and it follows the grid's view, filters and search.

```python
from lattice.api import TimelineSpec, build_timeline

WORKLOAD = TimelineSpec(
    "showcase.workload", "Surveyor visits", CLAIMS_GRID,
    start="visit_from", end="inspected_at", lane="surveyor",
    label="{claim_number} · {insured}", tone="severity", href="/showcase/claims/{id}")
```

List it in the manifest's `timelines=`, and put it on a page:

```python
timeline=build_timeline(request, WORKLOAD, linked=False, fixed={"event_code": "CAT-2610"})
```

```jinja
{% from "components/timeline.html" import timeline %}
{{ timeline(timeline) }}
```

## One row, one bar

| Option | Means |
|---|---|
| `start` | Timestamp column where the bar starts. Rows without one are left out |
| `end` | Timestamp column where it ends. **Null: still going**, drawn to now with an open end. Without an `end` column, every row is a marker |
| `lane` | Column grouping bars into lanes; its `Column.labels` name them |
| `label` | Bar text and tooltip, formatted with the row |
| `tone` | Column whose `Column.tones` colour the bar |
| `marker` | Column: when true, the row is a diamond at `start` (a report arrived, a worker was lost) |
| `href` | A click opens this, formatted with the row. Without it, a click opens the row in the linked grid's side panel, where its actions are |
| `lane_order` | `"start"`: lanes in order of their first bar (default); `"lane"`: by value |
| `limit` | Bars per window (2,000); past it, the timeline asks to zoom in |
| `poll_seconds` | Reload every n seconds, so open bars grow |

**Several bars in one lane are several rows.** A task that waited, ran, failed
and ran again is four rows with the same lane. Write the query to return one
row per phase: `apps/showcase/lattice_showcase/sql/claims.sql` (`progress`)
turns a claim's timestamps into waiting, with the surveyor, settling and
closing, and adds field reports as markers in a second lane. Bars that overlap
in a lane stack in rows.

## Window and zoom

Without a window the timeline shows every bar. Drag across a lane to zoom:
the browser asks for `from` and `to`, and the server returns only the bars that
overlap them, up to `limit`. **Reset zoom** returns to the whole range. A
dashed line marks now.

Times are UTC in the database, naive or `timestamptz`, and show in the
browser's time zone.

## Keyboard

Bars are buttons: Tab reaches them, left and right arrows move along a lane, up
and down move to the nearest bar in the next lane, and Enter opens one.

## In the showcase

| Page | Timeline |
|---|---|
| Events | The year's events: watch, then response, and a marker when closed. The live ones run to now |
| A claim's page | How long each stage took, and when field reports came in |
| Deployment | Each surveyor's inspection visits; stacked bars are double-booked |
