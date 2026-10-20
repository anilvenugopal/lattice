-- Rows the showcase's tests create, and queries they use to check results.

-- name: add_event
-- An event for a test; returns its id.
INSERT INTO showcase.event (code, name, peril, status, starts_on, landfall_on)
VALUES (:code, :name, 'hurricane', :status, DATE '2026-10-01', DATE '2026-10-02')
RETURNING id;

-- name: add_claim
-- A claim on one of the test book's locations; returns its id.
INSERT INTO showcase.claim (claim_number, event_id, location_id, loss_date, reported_at, channel,
  cause, severity, status, estimate, handler_id)
SELECT :claim_number, :event_id, l.id, DATE '2026-10-02', TIMESTAMP '2026-10-03 09:00',
       'phone', 'wind', :severity, :status, :estimate, :handler_id
FROM showcase.location l WHERE l.ref = :location_ref
RETURNING id;

-- name: claim
-- One claim.
SELECT id, status, priority, zone_id, handler_id FROM showcase.claim WHERE id = :id;



-- name: audit_events
-- Audit events with this action.
SELECT target_id, at FROM lattice.audit_event WHERE action = :action;

-- name: preference
-- One saved preference.
SELECT value FROM lattice.user_preference WHERE user_id = :user_id AND key = :key;

-- name: count_handled
-- How many claims have a desk handler.
SELECT count(*) FROM showcase.claim WHERE handler_id IS NOT NULL;

-- name: event_summary
-- Each event's status, footprint versions and claims, for the seed test.
SELECT e.code, e.status,
       (SELECT count(*) FROM showcase.footprint f WHERE f.event_id = e.id) AS footprints,
       (SELECT count(*) FROM showcase.claim c WHERE c.event_id = e.id) AS claims
FROM showcase.event e ORDER BY e.code;

-- name: delta_exposure
-- Hurricane Delta's exposed insured value at each advisory.
SELECT f.version, r.tiv
FROM showcase.exposure_run r
JOIN showcase.footprint f ON f.id = r.footprint_id
JOIN showcase.event e ON e.id = r.event_id
WHERE e.code = 'CAT-2610' ORDER BY f.version;

-- name: count_locations
-- How many insured locations the snapshot holds.
SELECT count(*) FROM showcase.location;

-- name: add_zone
-- A zone for an event, for the claims tests; returns its id.
INSERT INTO showcase.zone (event_id, name) VALUES (:event_id, :name) RETURNING id;

-- name: add_surveyor
-- A surveyor, for the claims tests; returns the id.
INSERT INTO showcase.staff (name, role, team, home) VALUES (:name, 'surveyor', 'Test', 'Houston')
RETURNING id;

-- name: claims_of
-- An event's claims.
SELECT id, claim_number, status, surveyor_id, zone_id FROM showcase.claim
WHERE event_id = :event_id ORDER BY id;

-- name: claim_event
-- A claim's event.
SELECT event_id FROM showcase.claim WHERE id = :id;

-- name: close_event
-- Close an event on a day, for the timeline tests.
UPDATE showcase.event SET closed_on = :closed_on WHERE id = :id;
