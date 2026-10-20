-- Catastrophe events (events.py).

-- name: grid
-- Every event with its latest footprint's exposure, and its claims so far.
SELECT e.id, e.code, e.name, e.peril, e.status, e.region, e.pcs_code, e.starts_on,
       e.landfall_on, e.closed_on, e.details,
       r.locations AS exposed_locations, r.tiv AS exposed_tiv,
       coalesce(c.claims, 0) AS claims, coalesce(c.open_claims, 0) AS open_claims,
       coalesce(c.incurred, 0) AS incurred
FROM showcase.event e
LEFT JOIN LATERAL (
  SELECT r.locations, r.tiv FROM showcase.exposure_run r
  WHERE r.event_id = e.id AND r.status = 'done'
  ORDER BY r.footprint_id DESC, r.id DESC LIMIT 1) r ON true
LEFT JOIN LATERAL (
  SELECT count(*) AS claims,
         count(*) FILTER (WHERE c.status NOT IN ('settled', 'closed')) AS open_claims,
         sum(c.estimate) AS incurred
  FROM showcase.claim c WHERE c.event_id = e.id) c ON true;

-- name: create
-- Declare an event; returns its id. The code is CAT- and the next number.
INSERT INTO showcase.event (code, name, peril, status, region, starts_on, details)
VALUES ('CAT-' || to_char(lattice.utc_now(), 'YY') ||
        lpad(CAST((SELECT count(*) + 1 FROM showcase.event) AS text), 2, '0'),
        :name, :peril, 'watch', :region, :starts_on, :details)
RETURNING id;

-- name: advance
-- Move events to their next stage: watch → landfall → response → recovery → closed.
UPDATE showcase.event
SET status = CASE status WHEN 'watch' THEN 'landfall' WHEN 'landfall' THEN 'response'
                         WHEN 'response' THEN 'recovery' ELSE 'closed' END,
    landfall_on = CASE WHEN status = 'watch' THEN CAST(lattice.utc_now() AS date) ELSE landfall_on END,
    closed_on = CASE WHEN status = 'recovery' THEN CAST(lattice.utc_now() AS date) ELSE closed_on END,
    updated_at = lattice.utc_now()
WHERE id = ANY(:ids) AND status <> 'closed';

-- name: footprints
-- An event's footprint versions, newest first, with what each one's exposure run found.
SELECT f.id, f.version, f.label, f.source, f.layer, f.created_at,
       r.status AS run_status, r.progress, r.locations, r.tiv
FROM showcase.footprint f
LEFT JOIN LATERAL (
  SELECT status, progress, locations, tiv FROM showcase.exposure_run
  WHERE footprint_id = f.id ORDER BY id DESC LIMIT 1) r ON true
WHERE f.event_id = :event_id
ORDER BY f.version DESC;

-- name: latest_footprint
-- An event's current footprint: its latest version.
SELECT id, version, label, layer FROM showcase.footprint
WHERE event_id = :event_id ORDER BY version DESC LIMIT 1;

-- name: latest_footprint_of
-- The current footprint of the event with this code.
SELECT f.id, f.version, f.label, f.layer FROM showcase.footprint f
JOIN showcase.event e ON e.id = f.event_id
WHERE e.code = :code ORDER BY f.version DESC LIMIT 1;

-- name: add_footprint
-- A new footprint version for an event; returns its id and version.
INSERT INTO showcase.footprint (event_id, version, label, source, layer)
VALUES (:event_id,
        (SELECT coalesce(max(version), 0) + 1 FROM showcase.footprint WHERE event_id = :event_id),
        :label, :source, :layer)
RETURNING id, version;

-- name: set_footprint_layer
-- Point a footprint at the geoengine layer its shapes were stored in.
UPDATE showcase.footprint SET layer = :layer WHERE id = :id;

-- name: queue_exposure
-- Queue an exposure run of a footprint; the background task runs it.
INSERT INTO showcase.exposure_run (event_id, footprint_id) VALUES (:event_id, :footprint_id)
RETURNING id;

-- name: areas
-- Saved areas, for choosing a footprint.
SELECT name, layer FROM showcase.area ORDER BY name;

-- name: add_area
-- Keep a drawn area; returns its id.
INSERT INTO showcase.area (name, layer, created_by) VALUES (:name, :layer, :created_by)
RETURNING id;

-- name: area_by_name
-- A saved area by name.
SELECT name, layer FROM showcase.area WHERE name = :name;

-- name: county_list
-- Counties of the states with insured locations, for choosing a footprint by county.
SELECT DISTINCT county_fips, county, state FROM showcase.location ORDER BY state, county;

-- name: by_id
-- One event.
SELECT id, code, name, peril, status, region FROM showcase.event WHERE id = :id;

-- name: stages
-- Each event's stages as bars for the timeline: watch until landfall, then the response
-- (still going until the event closes), and a marker when it closed.
SELECT e.id * 10 + 1 AS id, e.id AS event_id, e.code || ' · ' || e.name AS event,
       'watch' AS stage, 'Watch' AS stage_label, e.starts_on AS starts_at,
       coalesce(e.landfall_on, e.closed_on) AS ends_at, false AS is_marker
FROM showcase.event e
UNION ALL
SELECT e.id * 10 + 2, e.id, e.code || ' · ' || e.name, 'response', 'Response',
       e.landfall_on, e.closed_on, false
FROM showcase.event e WHERE e.landfall_on IS NOT NULL
UNION ALL
SELECT e.id * 10 + 3, e.id, e.code || ' · ' || e.name, 'closed', 'Closed',
       e.closed_on, CAST(NULL AS date), true
FROM showcase.event e WHERE e.closed_on IS NOT NULL;
