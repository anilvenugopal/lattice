---
title: Not built yet
summary: Charts, graphs and generated forms are planned but do not exist yet. What is planned, where each stands, and what to use meanwhile.
order: 110
keywords: charts chart.js graphs flows svelte flow xyflow dag stepper tree json schema forms form builder roadmap planned missing
---

Some components you might expect are **planned but not built**. They are not
in the code, the demo app has no example of them, and `lattice.api` does not
offer them. This page says what each will be, where it stands, and what to use
until then.

| Component | Status | Step of the plan |
|---|---|---|
| Charts | Decided ([ADR 0004](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0004-charts-chartjs.md), accepted) | 7 |
| Graphs, flows and trees | Proposed; needs a trial first ([ADR 0005](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0005-graphs-xyflow-web-component.md)) | 8 |
| Forms generated from JSON Schema | Proposed ([ADR 0007](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0007-json-schema-forms.md)) | 9 |

Steps 2 to 6 come first: Postgres, permissions, links between apps, grid data
sources and the taskline app. The full order is in
[Decisions and direction](../architecture/decisions.md).

## Charts

**Planned:** a chart component built on Chart.js 4, vendored like HTMX, so
there is no build step. It comes with plugins for:

- time series, with zoom and pan;
- maps (choropleth and bubble);
- calendar heatmaps and matrices;
- treemaps and flows (sankey);
- threshold lines and markers.

An app will declare a chart in Python, as it declares a grid:

- **One spec.** A `ChartSpec` names the chart type, the x and y values, the
  aggregation and the grouping.
- **Database aggregation.** The database does the counting and grouping; the
  browser only draws.
- **Linked to a grid.** A chart on the same page as a grid can share its view
  and filters, so both change together.
- **Theme colours.** Colours come from the theme, including status tones, so
  charts work in light and dark.

**Until then:** there is no chart support. For counts on a page, use `stat`
tiles (see [UI components](ui-components.md)) or home page tiles
(`HomeTile`). For a progress figure, use the `progress` macro or a grid column
of kind `progress`.

## Graphs, flows and trees

**Planned:** three components, from simplest to richest:

| Component | Built with | For |
|---|---|---|
| **Stepper** | HTML and CSS only | Linear flows: the steps of a job, the stages of a process |
| **Tree** | HTML and CSS, collapsible | Hierarchies: a parent run and its child runs |
| **Graph** | Svelte Flow with automatic layout, packaged as a web component `<lt-graph>` | Networks and process maps where users click through to records and act from the graph |

**Before the graph is adopted,** a trial must show that it:

- works inside Lattice's pages;
- follows light and dark mode;
- lays out 200 nodes smoothly;
- can be used from the keyboard;
- has an acceptable file size.

If the trial fails, React Flow is the fallback.

**Until then:** for a linear history, use the `timeline` macro, which shows a
record's activity. For anything else there is no component.

## Forms generated from JSON Schema

**Planned:** a form drawn automatically from a description of the data (JSON
Schema), which edits a JSON document and saves it back.

- **Fields from the data.** A form appears from a Pydantic model or a sample
  document, with no template to write.
- **Nothing lost.** Fields the schema does not describe are kept and returned
  unchanged.
- **Layout hints.** Order, sections and labels are kept apart from the schema.
- **Server validation.** The server checks the data against the schema before
  saving.
- **A form builder** will come later, when two apps need it.

**Until then:** build forms by hand from the field macros (`field`,
`select_field`, `checkbox`), as the demo's "New work item" page and the
[Your first app](../getting-started/first-app.md) tutorial do. See
[Forms and feedback](forms-and-feedback.md). This is the right choice for
most record forms even after generated forms exist.
