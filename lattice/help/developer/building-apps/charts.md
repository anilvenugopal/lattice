---
title: Charts
summary: Draw a grid's rows as a bar, line, area, pie, calendar, treemap, sankey or map chart, counted in the database and following the grid's filters.
order: 22
keywords: chart chartspec chart.js bar line area pie doughnut calendar heatmap histogram exceedance probability matrix treemap sankey map choropleth geo time series zoom threshold aggregate count sum average dashboard
---

A chart draws the rows of a grid you already have. It reads the grid's query,
narrows it by the grid's view, filters and search, and groups it in the
database. The browser only draws the result.

```python
from lattice.api import ChartSpec, Count, Sum, Threshold, Time

BY_WEEK = ChartSpec(
    key="showcase.work_by_week", title="Received per week", source=WORK_GRID,
    kind="bar", x=Time("created_at", "week"), series="status", stacked=True)

BY_LINE = ChartSpec(
    key="showcase.amount_by_line", title="Amount by line", source=WORK_GRID,
    kind="bar", x="line", y=Sum("amount", "Amount"), format="money", horizontal=True)
```

List the charts in the manifest, as for grids:

```python
APP = AppManifest(key="showcase", …, grids=[WORK_GRID], charts=[BY_WEEK, BY_LINE])
```

## Put a chart on a page

Build its context in the route, and place it with the `chart` macro:

```python
@router.get("/work/insights")
def insights(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "showcase/insights.html", "work.insights",
                       grid=build_grid(request, db, WORK_GRID),
                       charts=[build_chart(request, BY_WEEK), build_chart(request, BY_LINE)])
```

```jinja
{% from "components/chart.html" import chart %}
{% from "components/grid.html" import data_grid %}

<div class="chart-row">{% for c in charts %}{{ chart(c) }}{% endfor %}</div>
{{ data_grid(grid) }}
```

`chart-row` lays charts out side by side, wrapping on narrow screens.

## Linked to the grid

A chart and a grid with the same source on one page move together. Choose a
view tab, filter or search the grid, and the charts redraw for the same rows.
Saved views work the same way.

- **`build_chart(request, chart)`** links by default, and starts from the
  grid's state in the page address.
- **`linked=False`** draws the grid's default rows and ignores the grid.
- **`fixed={"customer_id": 42}`** narrows the rows for good, as for an
  [embedded grid](grids.md#fix-it-to-the-record-with-fixed): a chart of one
  customer's tickets on the customer's page.

A chart with no grid on its page still needs a `GridSpec` for its rows. Declare
one and list it in `grids=` without placing it on a page.

## Click to narrow the list

Clicking a bar, slice, treemap box or calendar day narrows the rows to it, by
the chart's `x` and `series` columns. A `Time` by day narrows a timestamp
column to that whole day. Histograms, exceedance curves, sankeys and world maps
are not clickable.

- **A linked chart** narrows the grid on its page in place. The grid shows each
  narrowing as a chip (*Construction: Frame*) that removes it.
- **`drill="/showcase/claims"`** on a chart without a grid on its page opens
  that list page instead, narrowed by `x_` parameters in the address, with the
  same chips. The event page's claims calendar does this.

```python
ChartSpec("showcase.claims_calendar", "Claims calendar", GRID, "calendar",
          x=Time("reported_at", "day"), drill="/showcase/claims")
```

## Kinds

| `kind` | `x` | `series` | Draws |
|---|---|---|---|
| `bar` | a column or `Time` | optional: one bar colour per value | Bars; `stacked=True`, `horizontal=True` |
| `line`, `area` | a column or `Time` | optional: one line per value | Lines, or filled areas; `stacked=True` for areas |
| `pie`, `doughnut` | a column | none | Slices |
| `calendar` | `Time(column, "day")` | none | One month as a calendar, each day shaded and labelled with its value. It opens on the month of the busiest day; ‹ › step through the months that have data |
| `histogram` | a numeric column | none | How many rows fall in each of `bins` (20) equal ranges |
| `exceedance` | a numeric column | none | The chance a value is exceeded, from 100% at the smallest to 0% at the largest; `thresholds` mark probabilities, such as `Threshold(1, "1 in 100")` |
| `treemap` | a column | optional: boxes grouped by it | Nested boxes sized by the measure |
| `sankey` | the "from" column | the "to" column (required) | Flows between the values of two columns |
| `choropleth` | a column of country names or ISO 3166 numeric codes | none | A world map shaded by the measure |

`create_app` refuses a chart whose kind doesn't fit its `x` and `series`.

## What is measured

| `y` | Per group |
|---|---|
| `Count()` (the default) | The number of rows |
| `Sum("amount", "Amount")` | The total of a column |
| `Avg(…)`, `Min(…)`, `Max(…)` | The average, smallest or largest value |

The second argument is the label in tooltips and legends.

**Time.** `Time("created_at", "week")` groups by `date_trunc`. Units: `hour`,
`day`, `week`, `month`, `quarter`, `year`. Users zoom a time chart by dragging
across it (Ctrl+wheel also zooms; Shift-drag pans); **Reset zoom** undoes it.

**Many categories.** Bar, pie and treemap charts on a category show the `limit` (12) largest values (line and area charts keep every value, in order, as an axis). With
`Count` or `Sum`, the rest add up to one **Other**, drawn grey. With an average,
minimum or maximum, the rest are left out.

## Options

| Field | Use |
|---|---|
| `thresholds=[Threshold(40, "Target", "danger")]` | A dashed line across a bar, line or area chart |
| `format` | `number` (default), `money` or `percent`: tooltips and the value axis |
| `height` | Pixels; default 280 |
| `permission` | Who may see it, on top of the grid's own permission |
| `empty_text` | Shown when no rows match |

## Colours

Charts are calm by default: one hue, with colour kept for what means something
([ADR 0015](/help/lattice/developer/architecture/decisions)). Choose a mode with
`colors=`:

| `colors=` | Draws | Use when |
|---|---|---|
| `"brand"` (default) | One series in the theme's brand colour; several series, slices or boxes in shades of it, darkest for the largest | Almost always |
| `"neutral"` | The same in greys | Calm dashboards, print |
| `"tones"` | Each value in its `Column.tones` colour, as the grid's badges | Colour has a meaning: severity, status |
| `"categorical"` | Eight distinct colours | Series must be told apart: one line per event |

Charts that name no mode follow the host's `LATTICE_CHART_COLORS` (`brand` or
`neutral`).

**Highlight instead of decorating.** A highlight draws the matching bars, slices
or boxes in a tone and every other one in muted grey:

```python
from lattice.api import Highlight

ChartSpec("showcase.claims_estimate", "Estimated loss by severity", GRID, "bar",
          x="severity", y=Sum("estimate"), highlight=[Highlight(values=["total"], tone="danger")])
ChartSpec("showcase.locations_quality", "Location quality", GRID, "doughnut", x="quality",
          highlight=[Highlight(values=["zip", "county"], tone="warning")])
```

`Highlight(above=1_000_000, tone="warning")` and `below=` match values instead of
keys. Highlights apply to single-series bars, pies, doughnuts and treemaps.

Colours come from tokens, in light and dark: `--chart-base` (the brand colour,
so a host theme that changes `--brand` changes every chart), `--chart-calm`,
`--chart-muted`, the tone colours and `--chart-1` to `--chart-8`. Apps name
modes and tones, never colours ([Styling](styling.md)). Maps shade in the base
colour, and timeline bars use it unless a tone column is named.

## Access

The chart reads only rows the grid's query returns for the user, so it never
counts a row its grid would not show. `GET /_chart/{key}/data` answers 403 to a
user without the grid's permission, or the chart's.

## How it is drawn

- **Chart.js 4** with its plugins (time scale, zoom, annotation, matrix,
  treemap, sankey and geo) is vendored in `static/js/vendor/chart/`. Exact
  versions are in its `VERSIONS` file.
- **Loaded on first use.** A page without a chart never downloads them, and
  each plugin loads only for its kind.
- **The world map** is Natural Earth's 1:110m countries, in
  `static/maps/countries-110m.json`.
