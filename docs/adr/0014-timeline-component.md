# 0014. Timelines: a TimelineSpec component drawn in HTML

Status: Accepted (19 October 2026)

## Context

Several apps need bars on a time axis, grouped in lanes:

- **Taskline UI** ([ADR 0012](0012-taskline-ui-and-contract.md)): a run's tasks as
  lanes, each with waiting, running and backoff bars, where the gaps between them are
  the point; workers as lanes, with the tasks they held and markers for `lost` and
  `requeued`; runs per queue over a window, which can be thousands.
- **The showcase**: a claim's progress and its field reports, surveyors' workloads,
  and the year's events by stage.
- **Incidents**, later: detected, acknowledged, mitigated, resolved.

Their shared needs: lanes of segments from a grid's rows; a bar with no end that
grows to "now"; markers; a "now" line; drag to zoom; click to open a record or act
on it; keyboard access; server-side windowing; colours from tokens.

## Decision

**A `TimelineSpec` component, like `MapSpec`, drawn as HTML elements**, not a
Chart.js chart kind:

- Chart.js draws on a canvas: bars cannot take keyboard focus, and markers, a moving
  "now" line and per-bar actions fight its model.
- HTML bars are positioned by percentage on lanes, are buttons (Tab, arrows,
  Enter), carry tooltips, and take colours from tokens. No new library.

**The rows are a grid's**, as for charts and maps: its query is the access
boundary, and the timeline follows the grid's view, filters and search.

- One row is one **segment**: `start`, `end` (null: still going, drawn to now),
  `lane`, `label`, and a tone from a status column's `Column.tones`. Several
  segments per lane are several rows; the query returns one row per phase.
- A row with `marker` set is drawn as a marker at its start.
- The data request carries the window (`from`, `to`); only overlapping rows come
  back, up to a limit, so zooming reloads only what is visible.
- A click opens the row's page (`href`), or the linked grid's side panel, where the
  grid's actions are.

Times are UTC from the database (naive or `timestamptz`), shown in the user's time
zone and time format.

## Not chosen

- **A Chart.js chart kind** (floating bars): no keyboard access; markers and
  per-bar actions are awkward. Recommended first, dropped once Taskline's needs
  were stated.
- **An editable Gantt** (drag to reschedule, dependencies, critical path): a
  planning tool, heavy to build, and no app needs it.

## Consequences

- Taskline UI's run view uses `TimelineSpec`; its temporary CSS bars are not needed
  if this lands first.
- The showcase records when claims were assigned, inspected and settled.
