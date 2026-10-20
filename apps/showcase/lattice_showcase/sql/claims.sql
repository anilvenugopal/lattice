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
