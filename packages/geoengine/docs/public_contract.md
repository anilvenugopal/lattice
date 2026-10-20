# geoengine: public contract

Everything another package may rely on. Anything not listed is internal and may change in
any release. `tests/test_public_contract.py` checks this document against the code and a
migrated database. Version: the package's (`geoengine.__version__`), semantic versioning;
before 1.0 a minor release may break the contract and a patch never does.

Requires Python 3.14+, PostgreSQL 18+ with PostGIS 3.6+. Coordinates are WGS 84
(EPSG:4326), longitude first in GeoJSON.

## Python names

| name | kind | parameters |
|---|---|---|
| migrate | function | target |
| schema_version | function | target |
| SCHEMA | constant | ("geo", migrations folder) |
| create_layer | function | conn, key, kind, name |
| delete_layer | function | conn, key |
| clear_layer | function | conn, layer_id |
| put_points | function | conn, layer_id, points |
| put_geojson | function | conn, layer_id, collection, id_property |
| as_geojson | function | conn, key |
| count | function | conn, key |
| cells | function | lat, lon |
| boundary | function | cell |
| RESOLUTIONS | constant | {5, 7, 9: description} |
| tier_for | function | precision |
| TIERS | constant | list of Tier |
| Tier | class | code, label, typical_error_m |
| to_geojson | function | topology, object_name |

## Tables in schema geo

Callers read these in their own SQL and write them only through the Python names above.

### geo.layer

| column | type |
|---|---|
| id | bigint |
| key | character varying |
| name | character varying |
| kind | character varying |
| created_at | timestamp with time zone |

### geo.feature

| column | type |
|---|---|
| id | bigint |
| layer_id | bigint |
| external_id | character varying |
| geom | geometry |
| props | jsonb |
| quality | character varying |
| h3_5 | character varying |
| h3_7 | character varying |
| h3_9 | character varying |

## SQL functions

| function | returns |
|---|---|
| geo.points_in(area_layer text, point_layer text) | point_id, area_id |
| geo.within_distance(point_layer text, area_layer text, meters double precision) | point_id, area_id, distance_m |

## Closed sets

| set | values |
|---|---|
| layer kind | points, areas |
| quality tier | rooftop, parcel, street, zip, county |
