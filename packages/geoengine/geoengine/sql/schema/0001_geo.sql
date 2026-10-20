-- geoengine's schema: layers of features (points or areas) in WGS 84 (EPSG:4326), and
-- the functions apps call from their own SQL. Needs PostGIS.

CREATE EXTENSION IF NOT EXISTS postgis;

-- A named set of features of one kind: a portfolio's locations, a fire perimeter, the
-- counties of a state, the forecast cone of one advisory.
CREATE TABLE geo.layer (
  id         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  key        varchar(128) NOT NULL UNIQUE,           -- chosen by the caller: "fire-2026-08"
  name       varchar(255) NOT NULL DEFAULT '',
  kind       varchar(16)  NOT NULL CHECK (kind IN ('points', 'areas')),
  created_at timestamptz  NOT NULL DEFAULT now()
);

-- One geometry. `external_id` is the caller's id for it (a location number, a county
-- code). Points carry their H3 cells and a location quality tier.
CREATE TABLE geo.feature (
  id          bigint                   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  layer_id    bigint                   NOT NULL REFERENCES geo.layer (id) ON DELETE CASCADE,
  external_id varchar(128)             NOT NULL,
  geom        geometry(Geometry, 4326) NOT NULL,
  props       jsonb                    NOT NULL DEFAULT '{}',
  quality     varchar(16)              CHECK (quality IN ('rooftop', 'parcel', 'street', 'zip', 'county')),
  h3_5        varchar(16),                            -- H3 cell, about 250 km² (a region)
  h3_7        varchar(16),                            -- about 5 km² (a town)
  h3_9        varchar(16),                            -- about 0.1 km² (a few blocks)
  UNIQUE (layer_id, external_id)
);
CREATE INDEX feature_geom ON geo.feature USING gist (geom);
CREATE INDEX feature_geog ON geo.feature USING gist (CAST(geom AS geography));
CREATE INDEX feature_h3_7 ON geo.feature (layer_id, h3_7);

-- Which points of one layer fall inside which areas of another.
CREATE FUNCTION geo.points_in(area_layer text, point_layer text)
RETURNS TABLE (point_id varchar, area_id varchar)
LANGUAGE sql STABLE AS $$
  SELECT p.external_id, a.external_id
  FROM geo.layer pl
  JOIN geo.feature p ON p.layer_id = pl.id
  JOIN geo.feature a ON ST_Intersects(a.geom, p.geom)
  JOIN geo.layer al ON al.id = a.layer_id
  WHERE pl.key = point_layer AND al.key = area_layer
$$;

-- Which points of one layer lie within `meters` of any feature of another, and how far
-- from the nearest one. Distances are on the earth's surface.
CREATE FUNCTION geo.within_distance(point_layer text, area_layer text, meters double precision)
RETURNS TABLE (point_id varchar, area_id varchar, distance_m double precision)
LANGUAGE sql STABLE AS $$
  SELECT DISTINCT ON (p.external_id)
         p.external_id, a.external_id,
         ST_Distance(CAST(p.geom AS geography), CAST(a.geom AS geography))
  FROM geo.layer pl
  JOIN geo.feature p ON p.layer_id = pl.id
  JOIN geo.layer al ON al.key = area_layer
  JOIN geo.feature a ON a.layer_id = al.id
   AND ST_DWithin(CAST(p.geom AS geography), CAST(a.geom AS geography), meters)
  WHERE pl.key = point_layer
  ORDER BY p.external_id, 3
$$;
