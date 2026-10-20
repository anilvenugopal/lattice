-- Rows the Comments tests create, and queries they use to check results.

-- name: add_location
-- A showcase insured location to put a claim on.
INSERT INTO showcase.location (ref, policy_number, insured, line, occupancy, construction,
  year_built, tiv, deductible, state, county_fips, county, city, snapshot_on)
VALUES (:ref, 'HO-1', 'Pat Pump', 'homeowners', 'single_family', 'frame', 2000, 300000, 1000,
        'TX', '48201', 'Harris', 'Houston', DATE '2026-10-19');

-- name: add_claim
-- A showcase claim to comment on, with its desk handler. Returns its id.
INSERT INTO showcase.claim (claim_number, location_id, loss_date, reported_at, channel, cause,
  severity, handler_id)
SELECT :claim_number, id, DATE '2026-10-02', TIMESTAMP '2026-10-03 09:00', 'phone', 'wind',
       'minor', :handler_id
FROM showcase.location WHERE ref = 'LOC-T1'
RETURNING id;

-- name: notifications_of
-- A user's notifications, newest first.
SELECT kind, title, body, subject FROM lattice.notification WHERE user_id = :owner_id ORDER BY id DESC;

-- name: comments_on
-- The comments on one record.
SELECT id, body, author_id FROM comments.comment WHERE subject = :subject ORDER BY id;
