# 0013. Geospatial: a separate geoengine package, PostGIS, and a Lattice map component

Status: Proposed (19 October 2026)

## Context

The next showcase is catastrophe event response for a P&C audience
([plan](../plans/step-10-cat-response-showcase.md)). It needs:

- insured locations as points, and areas such as a wildfire perimeter, a hurricane
  forecast cone or a set of counties;
- spatial work: which locations fall inside an area, distances and buffers, totals
  per hexagon, and a quality tier for each location (rooftop, parcel, zip centroid);
- maps: points, shaded regions, hexagons and areas over a background map, following
  a list's filters as charts do.

The owner wants the spatial work as its own package, knowing nothing of insurance or
of Lattice, so it can be reused and later published (`docs/misc/Geospatial Demo.txt`).

## Decision

**Three parts, the same split as Taskline ([ADR 0012](0012-taskline-ui-and-contract.md)):**

| Part | What it is | Depends on |
|---|---|---|
| **geoengine** (`packages/geoengine`, package `geoengine`) | Spatial data and computation: layers of points and areas, loading GeoJSON and CSV, point-in-area matching, distances and buffers, H3 hexagons, location quality tiers | Postgres with PostGIS; `h3` and `shapely` in Python. **Nothing of Lattice or of insurance** |
| **Lattice map component** (`MapSpec`, in `lattice.api`) | Draws points, shaded regions, hexagons and areas over a basemap; linked to a grid's filters; colours from tokens | Nothing of geoengine. It draws what a named query returns |
| **The showcase** | Policies, insured values, events, exposure runs, the loss estimate | Lattice and geoengine |

**geoengine starts in the Lattice workspace**, with its own `pyproject.toml`, its
own Postgres schema `geo` and its own migrations, and an import rule that fails the
build if it imports Lattice or any app. It moves to its own repository
(`anilvenugopal/geoengine`) when it is stable or a second user appears: a copy and
a tag, as Taskline was moved.

**Its contract**, written in `packages/geoengine/docs/public_contract.md` with a
test as Taskline's is:

- **Tables an app writes and reads**, in schema `geo`: `layer` (a named set of
  features, with a kind such as `points` or `areas`), `feature` (one geometry,
  with an external id and JSON properties), and their H3 and quality columns.
- **SQL functions an app calls from its own named queries**, such as
  `geo.points_in(area_layer, point_layer)` and `geo.within_distance(…)`. Spatial
  joins therefore stay in plain named SQL, Lattice's rule.
- **Python functions** for what SQL does poorly: loading GeoJSON and CSV,
  computing H3 cells and their boundaries, assigning quality tiers.

**PostGIS** is the only database extension. The development image becomes
`postgis/postgis:18-3.6`, which is Postgres 18 with PostGIS included and reads the
existing data volume. **H3 is computed in Python** (`h3` 4.5) and stored as an
ordinary column, so there is no second extension and no custom image.

**The map component** is MapLibre GL JS 6.12 (BSD licence), vendored and loaded on
first use like Chart.js. `h3-js` draws hexagon outlines in the browser. Points are read through geoengine's
`geo.point` view (added during stage 1), whose coordinates are safe to filter on. A
`MapSpec` is declared on a grid like a `ChartSpec`:

```python
MapSpec("showcase.exposure", "Exposed locations", source=EXPOSURE_GRID,
        layers=[Points(lon="lon", lat="lat", color="tier"),
                Hexagons(cell="h3_7", value=Sum("tiv")),
                Regions(key="county_fips", value=Count(), map="us-counties")])
```

The database aggregates; the browser draws. Rows come through the grid's query, so
the map shows only what the grid would.

**The basemap is self-hosted.** A single Protomaps file (`.pmtiles`), an
OpenStreetMap extract of the United States, is served from Lattice's own static
files, with its fonts and icons. The browser reads only the parts it needs from our
server: no outside map service, no account or key, and it works offline. The file
is a few hundred MB, so it is not in git; `make maps` downloads it once. Maps show
"© OpenStreetMap contributors", as the licence requires. Without the file, maps
draw state and county outlines only.

## Consequences

- Spatial joins on tens of thousands of locations run in Postgres with indexes, as
  every other query does.
- geoengine has one consumer at first, so its interface may change when a second
  appears; its version and contract test make that visible.
- The dev database image changes; `make db-up` pulls it, and the data volume stays.
- One more vendored library (MapLibre 6, ES modules, about 1.1 MB) loads only on
  pages with a map, and needs WebGL2.

## Rejected

- **A separate geospatial web service** (the `geo-risk-engine` API in the misc
  note). In-process SQL is simpler and faster; a service can wrap geoengine later.
- **The h3-pg Postgres extension.** It needs a custom database image; Python's
  `h3` does the same job at load time.
- **deck.gl.** Built for millions of points with WebGL layers; heavier than we
  need, and MapLibre draws 50,000 points and hexagons comfortably.
- **Online tile services** (Mapbox, Google, public OpenStreetMap servers). Keys,
  costs, outside calls, no offline demo.
- **Leaflet.** Simple, but raster-first and weaker at many shaded shapes; MapLibre
  styles vector maps from our tokens, including dark mode.
