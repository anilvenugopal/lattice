-- Claims copied from the claims system (claims.py).

-- name: grid
-- Every claim with its event, location, zone and people.
SELECT c.id, c.claim_number, c.event_id, e.code AS event_code, e.name AS event,
       c.loss_date, c.reported_at, c.channel, c.cause, c.severity, c.status, c.priority,
       c.estimate, c.paid, c.zone_id, z.name AS zone, s.name AS surveyor, a.name AS adjuster,
       l.ref AS location_ref, l.insured, l.line, l.policy_number, l.county_fips, l.county,
       l.state, l.city, p.lon, p.lat, p.quality, p.h3_7,
       CAST(c.reported_at AS date) - e.landfall_on AS days_after,
       c.updated_at
FROM showcase.claim c
JOIN showcase.location l ON l.id = c.location_id
JOIN geo.point p ON p.layer = 'locations' AND p.external_id = l.ref
LEFT JOIN showcase.event e ON e.id = c.event_id
LEFT JOIN showcase.zone z ON z.id = c.zone_id
LEFT JOIN showcase.staff s ON s.id = c.surveyor_id
LEFT JOIN showcase.staff a ON a.id = c.adjuster_id;

-- name: by_id
-- One claim with what its page needs beyond the grid row.
SELECT c.id, c.claim_number, c.event_id, c.status, c.severity, c.estimate, c.paid, c.cause,
       l.line, l.tiv, l.deductible, l.occupancy, l.construction, l.ref AS location_ref
FROM showcase.claim c JOIN showcase.location l ON l.id = c.location_id
WHERE c.id = :id;

-- name: zone_options
-- Zones of active events, for assigning claims.
SELECT z.id, e.code || ' · ' || z.name AS label
FROM showcase.zone z JOIN showcase.event e ON e.id = z.event_id
WHERE e.status <> 'closed' ORDER BY e.code, z.name;

-- name: surveyor_options
-- Surveyors, for assigning claims.
SELECT id, name || ' (' || home || ')' AS label FROM showcase.staff
WHERE role = 'surveyor' ORDER BY name;

-- name: assign_zone
-- Put claims in a zone.
UPDATE showcase.claim SET zone_id = :zone_id, updated_at = lattice.utc_now()
WHERE id = ANY(:ids);

-- name: assign_surveyor
-- Give claims a surveyor; new claims become assigned.
UPDATE showcase.claim
SET surveyor_id = :surveyor_id, updated_at = lattice.utc_now(),
    status = CASE WHEN status = 'new' THEN 'assigned' ELSE status END
WHERE id = ANY(:ids);

-- name: prioritise
-- Flag claims as priority, or clear the flag.
UPDATE showcase.claim SET priority = :priority, updated_at = lattice.utc_now()
WHERE id = ANY(:ids);

-- name: mark_inspected
-- Record that claims were inspected.
UPDATE showcase.claim SET status = 'inspected', updated_at = lattice.utc_now()
WHERE id = ANY(:ids) AND status IN ('new', 'assigned');

-- name: intake
-- The intake simulator's controls.
SELECT running, per_minute FROM showcase.intake WHERE id = 1;

-- name: set_intake
-- Start, pause or change the speed of the intake simulator.
UPDATE showcase.intake SET running = :running, per_minute = :per_minute,
       updated_at = lattice.utc_now()
WHERE id = 1;

-- name: live_event
-- The event the simulator feeds: the most recent one in response.
SELECT id, code, name FROM showcase.event WHERE status IN ('landfall', 'response')
ORDER BY landfall_on DESC NULLS LAST, id DESC LIMIT 1;

-- name: intake_candidates
-- Exposed locations of an event without a claim yet, to draw new claims from.
SELECT l.id, l.tiv, l.county_fips
FROM showcase.exposure_run r
JOIN showcase.exposure x ON x.run_id = r.id
JOIN showcase.location l ON l.id = x.location_id
WHERE r.id = (SELECT id FROM showcase.exposure_run WHERE event_id = :event_id AND status = 'done'
              ORDER BY footprint_id DESC, id DESC LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM showcase.claim c WHERE c.location_id = l.id AND c.event_id = :event_id)
ORDER BY random()
LIMIT :limit;

-- name: next_claim_number
-- The next claim number's sequence part.
SELECT coalesce(max(CAST(split_part(claim_number, '-', 3) AS integer)), 0) + 1 FROM showcase.claim;

-- name: zones_of
-- An event's zones with their counties, for placing new claims.
SELECT z.id, z.name FROM showcase.zone z WHERE z.event_id = :event_id;

-- name: deployment
-- An event's zones, their leads, surveyors and claim counts, for the deployment graph.
SELECT z.id AS zone_id, z.name AS zone, lead.name AS lead, s.id AS surveyor_id,
       s.name AS surveyor, count(c.id) AS claims,
       count(c.id) FILTER (WHERE c.status IN ('new', 'assigned')) AS waiting,
       count(c.id) FILTER (WHERE c.priority) AS priority
FROM showcase.zone z
LEFT JOIN showcase.staff lead ON lead.id = z.lead_id
LEFT JOIN showcase.claim c ON c.zone_id = z.id
LEFT JOIN showcase.staff s ON s.id = c.surveyor_id
WHERE z.event_id = :event_id
GROUP BY z.id, z.name, lead.name, s.id, s.name
ORDER BY z.name, s.name NULLS FIRST;

-- name: zones_grid
-- Zones with their open, waiting and priority claims, for zone actions.
SELECT z.id, z.name, e.code AS event_code, z.event_id,
       count(c.id) FILTER (WHERE c.status NOT IN ('settled', 'closed')) AS open_claims,
       count(c.id) FILTER (WHERE c.status IN ('new', 'assigned')) AS waiting
FROM showcase.zone z
JOIN showcase.event e ON e.id = z.event_id
LEFT JOIN showcase.claim c ON c.zone_id = z.id
GROUP BY z.id, z.name, e.code, z.event_id;

-- name: prioritise_zone
-- Flag every waiting claim in zones as priority.
UPDATE showcase.claim SET priority = true, updated_at = lattice.utc_now()
WHERE zone_id = ANY(:ids) AND status IN ('new', 'assigned');
