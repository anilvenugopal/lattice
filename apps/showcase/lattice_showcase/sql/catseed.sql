-- Sample data for the catastrophe response story (cat_seed.py).

-- name: add_location
-- One insured location from the exposure snapshot; returns its id.
INSERT INTO showcase.location (ref, policy_number, insured, line, occupancy, construction,
  year_built, tiv, deductible, state, county_fips, county, city, snapshot_on)
VALUES (:ref, :policy_number, :insured, :line, :occupancy, :construction, :year_built, :tiv,
        :deductible, :state, :county_fips, :county, :city, :snapshot_on);

-- name: location_counties
-- The county each sample point fell in, from geoengine.
SELECT point_id, area_id FROM geo.points_in('us-counties', 'locations');

-- name: add_staff
-- One responder; returns the id.
INSERT INTO showcase.staff (name, role, team, home) VALUES (:name, :role, :team, :home)
RETURNING id;

-- name: add_event
-- One event; returns its id.
INSERT INTO showcase.event (code, name, peril, status, pcs_code, region, starts_on,
  landfall_on, closed_on, details)
VALUES (:code, :name, :peril, :status, :pcs_code, :region, :starts_on, :landfall_on,
        :closed_on, :details)
RETURNING id;

-- name: add_footprint
-- One footprint version; returns its id.
INSERT INTO showcase.footprint (event_id, version, label, source, layer, created_at)
VALUES (:event_id, :version, :label, :source, :layer, :created_at)
RETURNING id;

-- name: add_exposure_run
-- A finished exposure run of a footprint over the locations inside it; returns its id.
WITH run AS (
  INSERT INTO showcase.exposure_run (event_id, footprint_id, status, progress, started_at,
                                     finished_at, created_at)
  VALUES (:event_id, :footprint_id, 'done', 100, :at, :at, :at)
  RETURNING id
), inside AS (
  INSERT INTO showcase.exposure (run_id, location_id)
  SELECT run.id, l.id
  FROM run, geo.points_in(:layer, 'locations') p
  JOIN showcase.location l ON l.ref = p.point_id
  RETURNING location_id
)
SELECT id FROM run;

-- name: total_exposure_run
-- Record a run's totals.
UPDATE showcase.exposure_run r
SET locations = t.n, tiv = t.tiv
FROM (SELECT count(*) AS n, coalesce(sum(l.tiv), 0) AS tiv
      FROM showcase.exposure e JOIN showcase.location l ON l.id = e.location_id
      WHERE e.run_id = :run_id) t
WHERE r.id = :run_id;

-- name: exposed
-- The locations of one exposure run, for drawing claims from.
SELECT l.id, l.line, l.tiv, l.county_fips, l.county
FROM showcase.exposure e JOIN showcase.location l ON l.id = e.location_id
WHERE e.run_id = :run_id
ORDER BY l.id;

-- name: add_zone
-- One response zone; returns its id.
INSERT INTO showcase.zone (event_id, name, lead_id) VALUES (:event_id, :name, :lead_id)
RETURNING id;

-- name: add_claim
-- One claim copied from the claims system.
INSERT INTO showcase.claim (claim_number, event_id, location_id, loss_date, reported_at,
  channel, cause, severity, status, priority, estimate, paid, zone_id, surveyor_id,
  adjuster_id, closed_at, updated_at)
VALUES (:claim_number, :event_id, :location_id, :loss_date, :reported_at, :channel, :cause,
        :severity, :status, :priority, :estimate, :paid, :zone_id, :surveyor_id, :adjuster_id,
        :closed_at, :updated_at);
