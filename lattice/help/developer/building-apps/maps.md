---
title: Maps
summary: Draw a grid's rows on a map as points, hexagons or shaded states and counties, with areas such as a fire perimeter, over a self-hosted basemap.
order: 23
keywords: map mapspec maplibre points hexagons h3 regions counties states choropleth areas geojson basemap protomaps pmtiles geospatial geoengine
---

A map draws the rows of a grid you already have, like a [chart](charts.md). It
reads the grid's query, narrowed by its view, filters and search; the database
groups it; the browser draws it with MapLibre.

```python
from lattice.api import Areas, Hexagons, MapSpec, Points, Regions, Sum

EXPOSURE = MapSpec("showcase.exposure", "Exposed locations", source=LOCATIONS_GRID,
                   format="money", layers=[
    Regions("county_fips", Sum("tiv", "Insured value"), map="us-counties"),
    Hexagons("h3_7", Sum("tiv", "Insured value")),
    Points("lon", "lat", color="quality", label="{ref}"),
    Areas("footprint", "Footprint", load=footprint, tone="danger"),
])

APP = AppManifest(key="showcase", …, grids=[LOCATIONS_GRID], maps=[EXPOSURE])
```

Place it as a chart is placed:

```python
return render_page(request, "showcase/exposure.html", "exposure",
                   grid=build_grid(request, db, LOCATIONS_GRID), m=build_map(request, EXPOSURE))
```

```jinja
{% from "components/map.html" import map_view %}
{{ map_view(m) }}
```

`build_map` links the map to the grid on the same page, and takes `linked=False`
and `fixed={…}` exactly as [`build_chart`](charts.md#linked-to-the-grid) does.

## Layers

Drawn bottom to top. The legend in the map's header turns each on and off.

| Layer | Draws | Needs in the grid's query |
|---|---|---|
| `Points(lon, lat, color, label)` | A dot per row. `color` names a column: its `Column` tones colour the dots (a status, a quality tier), else a fixed palette. `label` is the popup text, formatted with the row | Longitude and latitude (WGS 84) |
| `Hexagons(cell, value)` | A measure per H3 cell, shaded faint to strong | An H3 cell id per row, such as geoengine's `h3_7` |
| `Regions(key, value, map)` | A measure per US state (`us-states`) or county (`us-counties`), shaded | The FIPS code: 2 digits for a state, 5 for a county |
| `Areas(key, title, load, tone)` | Shapes from a function, not the grid: a fire perimeter, a forecast cone | — `load(db, user)` returns a GeoJSON FeatureCollection |

`value` takes the chart measures: `Count()` (default), `Sum`, `Avg`, `Min`,
`Max`. `Points` draws at most `limit` dots (20,000), and says so when it cuts.

Hover any shape or dot for its value or label.

## Draw to search

On a map linked to a grid that declares its coordinates, users draw a **polygon**,
**rectangle** or **circle**, and the grid narrows to the rows inside. Its count,
totals, charts and the map's own layers follow, because they all read the grid's
state:

```python
LOCATIONS_GRID = GridSpec(key="showcase.locations", …, spatial=("lon", "lat"))
```

- **The shape is a filter.** It travels in the page address as `shape` (GeoJSON),
  so a link or a [saved view](grids.md#shared-endpoints) reopens it. The grid's
  toolbar shows **Inside drawn shape ×** to clear it.
- **In the database:** the grid's query gains one PostGIS condition, the point
  `(lon, lat)` inside the shape. The host's database therefore needs PostGIS.
- **Limits:** one shape at a time; at most 2,000 points (a circle is a polygon of
  64). Drawing uses Terra Draw (MIT), loaded the first time someone draws.

Keeping a drawn shape (as a named area, say) is the app's job: the map sends it
to the grid; an app action can store it with geoengine.

## Spatial work: geoengine

The map only draws. Matching points to areas, distances, H3 cells and location
quality tiers are the job of **geoengine**, a separate package in
`packages/geoengine` that knows nothing of Lattice
([ADR 0013](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0013-geoengine-and-maps.md)).
An app that uses it lists its schema, so `lattice migrate` creates it:

```python
import geoengine
APP = AppManifest(key="showcase", …, library_schemas=[geoengine.SCHEMA])
```

and reads its points and matches in its own named queries:

```sql
-- name: exposed
-- Locations inside an event's footprint.
SELECT p.feature_id AS id, p.external_id AS ref, p.lon, p.lat, p.quality, p.h3_7
FROM geo.point p
JOIN geo.points_in(:footprint, 'locations') m ON m.point_id = p.external_id
WHERE p.layer = 'locations';
```

Read coordinates from `geo.point`, never `ST_X(geom)` on `geo.feature`. Its
contract is `packages/geoengine/docs/public_contract.md`.

## The basemap

With the basemap, maps show coastlines, roads, places and labels; without it,
states and county lines on a plain background. Both follow light and dark mode.

The basemap is self-hosted: one Protomaps file, an OpenStreetMap extract of the
contiguous United States, served from `static/maps/basemap/` with its fonts and
icons. Browsers read only the parts they need, from our server: no outside map
service, no keys, and it works offline. It is about 400 MB, so it is not in git:

```bash
make maps
```

Maps credit "© OpenStreetMap contributors", as its licence requires.

## Colours and loading

- Data colours come from the `--chart-*` tokens; the plain background from
  `--map-land`, `--map-water` and `--map-line`.
- MapLibre (about 1.1 MB) and its helpers in `static/js/vendor/map/` load the
  first time a page shows a map. Exact versions are in its `VERSIONS` file.
- MapLibre needs WebGL2, which every current browser has.
