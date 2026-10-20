-- Points as plain columns, for callers' queries. Reading ST_X(geom) straight from
-- geo.feature can fail: Postgres may evaluate it on area rows of other layers before a
-- join removes them. This view computes coordinates in a way every geometry allows.

CREATE VIEW geo.point AS
SELECT l.key AS layer, f.external_id, f.id AS feature_id,
       ST_X(ST_Centroid(f.geom)) AS lon, ST_Y(ST_Centroid(f.geom)) AS lat,
       f.quality, f.h3_5, f.h3_7, f.h3_9, f.props
FROM geo.feature f
JOIN geo.layer l ON l.id = f.layer_id
WHERE l.kind = 'points';
