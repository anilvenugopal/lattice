# 0004. Charts with Chart.js and its plugins

Status: Accepted

## Context

Charts must be embeddable like grids and forms, so they are a core component.
Required kinds: standard charts, time series, geographic maps and calendar
heatmaps.

## Decision

- Chart.js 4, vendored with no build step, with these plugins (all MIT):
  - the time scale with `chartjs-adapter-date-fns`;
  - `chartjs-plugin-zoom`;
  - `chartjs-chart-geo`, with vendored TopoJSON maps;
  - `chartjs-chart-matrix`;
  - `chartjs-chart-treemap`;
  - `chartjs-chart-sankey`;
  - `chartjs-plugin-annotation`.
- A `ChartSpec` declares a chart on a data source (usually a grid's source): kind,
  x, y, aggregation and grouping. The database aggregates; the browser only draws.
- A chart can share a grid's view and filters on a page, so both change together.
- Colours come from the CSS tokens, including status tones, so charts follow the
  theme.

## Consequences

- No build step for charts.
- Geo maps need TopoJSON files in `static/`, a few hundred KB per map set.
- Graphs and DAGs are not drawn with Chart.js ([0005](0005-graphs-xyflow-web-component.md)).

## Rejected

- **ECharts.** It covers charts and graphs in one library, but is heavier, and
  graph interaction is handled by [0005](0005-graphs-xyflow-web-component.md).
- **Vega-Lite.** Declarative and good for generated specs, but heavier and
  further from the requested plugins.
