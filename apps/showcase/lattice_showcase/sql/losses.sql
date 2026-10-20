-- Monte Carlo loss estimates (losses.py).

-- name: samples
-- The simulated losses of an event's latest finished estimate. The page fixes event_id.
SELECT s.simulation AS id, s.loss, r.event_id
FROM showcase.loss_sample s
JOIN showcase.loss_run r ON r.id = s.run_id
WHERE r.id = (SELECT r2.id FROM showcase.loss_run r2
              WHERE r2.event_id = r.event_id AND r2.status = 'done' ORDER BY r2.id DESC LIMIT 1);

-- name: runs
-- Loss estimate runs, for the live list.
SELECT r.id, r.event_id, f.label AS footprint, r.simulations, r.status, r.progress,
       r.mean_loss, r.p99_loss, r.p996_loss, r.created_at, r.finished_at
FROM showcase.loss_run r JOIN showcase.footprint f ON f.id = r.footprint_id;

-- name: latest
-- An event's latest finished estimate.
SELECT id, simulations, assumptions, mean_loss, p99_loss, p996_loss, finished_at, footprint_id
FROM showcase.loss_run WHERE event_id = :event_id AND status = 'done'
ORDER BY id DESC LIMIT 1;

-- name: queue
-- Queue an estimate of an event's current footprint; returns its id.
INSERT INTO showcase.loss_run (event_id, footprint_id, simulations, assumptions)
SELECT :event_id, f.id, :simulations, :assumptions
FROM showcase.footprint f WHERE f.event_id = :event_id ORDER BY f.version DESC LIMIT 1
RETURNING id;

-- name: next_queued
-- The oldest queued estimate, taken for processing.
UPDATE showcase.loss_run SET status = 'running', started_at = lattice.utc_now(), progress = 1
WHERE id = (SELECT id FROM showcase.loss_run WHERE status = 'queued' ORDER BY id LIMIT 1
            FOR UPDATE SKIP LOCKED)
RETURNING id, event_id, footprint_id, simulations, assumptions;

-- name: inputs
-- What the model needs: the event's peril details, the footprint layer, and the exposed
-- locations of the footprint's exposure run.
SELECT l.id, p.lon, p.lat, l.tiv, l.deductible, l.construction
FROM showcase.exposure_run r
JOIN showcase.exposure x ON x.run_id = r.id
JOIN showcase.location l ON l.id = x.location_id
JOIN geo.point p ON p.layer = 'locations' AND p.external_id = l.ref
WHERE r.id = (SELECT id FROM showcase.exposure_run WHERE footprint_id = :footprint_id
              AND status = 'done' ORDER BY id DESC LIMIT 1);

-- name: event_peril
-- An event's peril and details.
SELECT e.peril, e.details, f.layer
FROM showcase.event e JOIN showcase.footprint f ON f.event_id = e.id
WHERE f.id = :footprint_id;

-- name: progress
-- Record an estimate's progress.
UPDATE showcase.loss_run SET progress = :progress WHERE id = :id;

-- name: add_sample
-- One simulation's loss.
INSERT INTO showcase.loss_sample (run_id, simulation, loss) VALUES (:run_id, :simulation, :loss);

-- name: finish
-- Finish an estimate with its summary figures.
UPDATE showcase.loss_run
SET status = 'done', progress = 100, finished_at = lattice.utc_now(),
    mean_loss = :mean_loss, p99_loss = :p99_loss, p996_loss = :p996_loss
WHERE id = :id;
