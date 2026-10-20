-- Layers and features (geoengine/layers.py).

-- name: create_layer
-- Create a layer, or rename an existing one with this key; returns its id.
INSERT INTO geo.layer (key, name, kind) VALUES (:key, :name, :kind)
ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name
RETURNING id, kind;

-- name: layer
-- One layer by key.
SELECT id, key, name, kind, created_at FROM geo.layer WHERE key = :key;

-- name: delete_layer
-- Delete a layer and its features.
DELETE FROM geo.layer WHERE key = :key;

-- name: clear_layer
-- Delete a layer's features, keeping the layer.
DELETE FROM geo.feature WHERE layer_id = :layer_id;

-- name: put_point
-- Add a point to a layer, or move it if its id is already there.
INSERT INTO geo.feature (layer_id, external_id, geom, props, quality, h3_5, h3_7, h3_9)
VALUES (:layer_id, :external_id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
        CAST(:props AS jsonb), :quality, :h3_5, :h3_7, :h3_9)
ON CONFLICT (layer_id, external_id) DO UPDATE
SET geom = EXCLUDED.geom, props = EXCLUDED.props, quality = EXCLUDED.quality,
    h3_5 = EXCLUDED.h3_5, h3_7 = EXCLUDED.h3_7, h3_9 = EXCLUDED.h3_9;

-- name: put_area
-- Add an area (a GeoJSON geometry) to a layer, or replace it; invalid shapes are repaired.
INSERT INTO geo.feature (layer_id, external_id, geom, props)
VALUES (:layer_id, :external_id,
        ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326)), CAST(:props AS jsonb))
ON CONFLICT (layer_id, external_id) DO UPDATE
SET geom = EXCLUDED.geom, props = EXCLUDED.props;

-- name: as_geojson
-- A layer's features as GeoJSON geometries, for a map.
SELECT f.external_id, ST_AsGeoJSON(f.geom, 6) AS geometry, f.props
FROM geo.feature f JOIN geo.layer l ON l.id = f.layer_id
WHERE l.key = :key
ORDER BY f.external_id;

-- name: count
-- How many features a layer has.
SELECT count(*) FROM geo.feature f JOIN geo.layer l ON l.id = f.layer_id WHERE l.key = :key;
