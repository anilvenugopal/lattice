# refdata

Public reference data loaded into Postgres (schema `ref`), with simple lookups. Today:
US towns and cities, counties and zip codes, from the Census gazetteer, to search a map
by. It knows nothing of Lattice or its apps, nor of geoengine.

It lives in the Lattice workspace for now and moves to its own repository when stable.
Everything another package may use is in [docs/public_contract.md](docs/public_contract.md).

```python
import refdata

refdata.migrate("postgresql+psycopg://…")    # the schema, then the bundled data
with engine.connect() as conn:
    refdata.search_places(conn, "Lake Charles, LA")
    # [{"kind": "place", "name": "Lake Charles", "state": "LA", "lon": -93.21, "lat": 30.2,
    #   "label": "Lake Charles, LA"}, …]
```

A Lattice app installs it through the migration hook, so `lattice migrate` creates the
schema and loads the data, and `lattice reset` drops it:

```python
APP = AppManifest(…, libraries=[Library("refdata", [refdata.SCHEMA], refdata.migrate)])
```

## The data

`refdata/data/us_places.csv.gz` (69,346 places, about 1 MB) is built by
`scripts/build_places.py` from the 2024 gazetteer files at
https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/
(`2024_Gaz_place_national`, `2024_Gaz_counties_national`, `2024_Gaz_zcta_national`;
public domain), keeping kind, name, state, the internal point and land area.

Tests: `uv run pytest packages/refdata/tests` (the server is `REFDATA_TEST_URL`, by default
the workspace's development Postgres).
