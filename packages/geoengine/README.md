# geoengine

Spatial data and computation on Postgres with PostGIS: layers of points and areas,
point-in-area matching and distances as SQL functions, H3 hexagons and location quality
tiers on every point. It knows nothing of Lattice or of insurance
([Lattice ADR 0013](../../docs/adr/0013-geoengine-and-maps.md)).

It lives in the Lattice workspace for now and moves to its own repository when stable.
Everything another package may use is in [docs/public_contract.md](docs/public_contract.md).

```python
import geoengine

geoengine.migrate("postgresql+psycopg://…")            # or a Lattice app's library_schemas
with engine.begin() as conn:
    homes = geoengine.create_layer(conn, "homes", "points")
    geoengine.put_points(conn, homes, [{"id": "L1", "lon": -95.2, "lat": 29.7,
                                        "quality": "rooftop"}])
    fire = geoengine.create_layer(conn, "fire-2026-08", "areas")
    geoengine.put_geojson(conn, fire, perimeter_geojson)
```

```sql
-- in the caller's own named query
SELECT point_id FROM geo.points_in('fire-2026-08', 'homes');
```

Tests: `uv run pytest packages/geoengine/tests` (needs PostGIS; the server is
`GEOENGINE_TEST_URL`, by default the workspace's development Postgres).
