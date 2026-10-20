-- Exposure runs and exposed locations (exposure.py).

-- name: grid
-- Locations in an event's latest finished exposure run, with their place and quality.
-- The page fixes event_id.
SELECT l.id, l.ref, l.policy_number, l.insured, l.line, l.occupancy, l.construction,
       l.year_built, l.tiv, l.deductible, l.state, l.county_fips, l.county, l.city,
       p.lon, p.lat, p.quality, p.h3_7, r.event_id
FROM showcase.exposure_run r
JOIN showcase.exposure x ON x.run_id = r.id
JOIN showcase.location l ON l.id = x.location_id
JOIN geo.point p ON p.layer = 'locations' AND p.external_id = l.ref
WHERE r.id = (SELECT r2.id FROM showcase.exposure_run r2
              WHERE r2.event_id = r.event_id AND r2.status = 'done'
              ORDER BY r2.footprint_id DESC, r2.id DESC LIMIT 1);

-- name: runs
-- Exposure runs of all events, for the live list.
SELECT r.id, e.code, e.name AS event, f.version, f.label AS footprint, r.status, r.progress,
       r.locations, r.tiv, r.created_at, r.started_at, r.finished_at, r.event_id
FROM showcase.exposure_run r
JOIN showcase.event e ON e.id = r.event_id
JOIN showcase.footprint f ON f.id = r.footprint_id;

-- name: next_queued
-- The oldest queued run, taken for processing.
UPDATE showcase.exposure_run SET status = 'running', started_at = lattice.utc_now(), progress = 5
WHERE id = (SELECT id FROM showcase.exposure_run WHERE status = 'queued' ORDER BY id LIMIT 1
            FOR UPDATE SKIP LOCKED)
RETURNING id, footprint_id;

-- name: footprint_layer
-- The geoengine layer of a footprint.
SELECT layer FROM showcase.footprint WHERE id = :id;

-- name: states_in
-- The states with locations in a footprint, to run one state at a time.
SELECT DISTINCT l.state
FROM geo.points_in(:layer, 'locations') p
JOIN showcase.location l ON l.ref = p.point_id
ORDER BY l.state;

-- name: add_state
-- Add one state's locations in a footprint to a run.
INSERT INTO showcase.exposure (run_id, location_id)
SELECT :run_id, l.id
FROM geo.points_in(:layer, 'locations') p
JOIN showcase.location l ON l.ref = p.point_id
WHERE l.state = :state
ON CONFLICT DO NOTHING;

-- name: progress
-- Record a run's progress.
UPDATE showcase.exposure_run SET progress = :progress WHERE id = :id;

-- name: finish
-- Finish a run with its totals.
UPDATE showcase.exposure_run r
SET status = 'done', progress = 100, finished_at = lattice.utc_now(),
    locations = t.n, tiv = t.tiv
FROM (SELECT count(*) AS n, coalesce(sum(l.tiv), 0) AS tiv
      FROM showcase.exposure x JOIN showcase.location l ON l.id = x.location_id
      WHERE x.run_id = :id) t
WHERE r.id = :id;
