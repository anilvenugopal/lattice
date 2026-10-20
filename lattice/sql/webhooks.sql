-- Webhooks (kernel/services/webhooks.py, ADR 0016 phase 3).

-- name: listening
-- Active webhooks that take this event type.
SELECT id, format FROM lattice.webhook
WHERE active AND (:event_type = ANY(events) OR '*' = ANY(events));

-- name: queue
-- Queue one post to a webhook.
INSERT INTO lattice.webhook_delivery (webhook_id, event_id, event_type, subject, body)
VALUES (:webhook_id, :event_id, :event_type, :subject, :body);

-- name: due
-- Posts due now, with their webhook's address and secret, taken by this sender alone.
SELECT d.id, d.body, d.attempts, w.url, w.secret, w.format
FROM lattice.webhook_delivery d JOIN lattice.webhook w ON w.id = d.webhook_id
WHERE d.status = 'queued' AND d.next_attempt_at <= lattice.utc_now()
ORDER BY d.next_attempt_at LIMIT 50
FOR UPDATE OF d SKIP LOCKED;

-- name: delivered
-- Record a post the receiver accepted.
UPDATE lattice.webhook_delivery
SET status = 'delivered', attempts = attempts + 1, response_status = :response_status,
    last_error = '', delivered_at = lattice.utc_now()
WHERE id = :id;

-- name: failed
-- Record a failed post: try again later, or give up after five.
UPDATE lattice.webhook_delivery
SET attempts = attempts + 1, response_status = :response_status, last_error = :error,
    status = CASE WHEN attempts + 1 >= 5 THEN 'failed' ELSE 'queued' END,
    next_attempt_at = lattice.utc_now() + make_interval(mins => CAST(power(2, attempts + 1) AS integer))
WHERE id = :id;

-- name: retry
-- Queue failed posts again.
UPDATE lattice.webhook_delivery SET status = 'queued', attempts = 0, next_attempt_at = lattice.utc_now()
WHERE id = ANY(:ids) AND status = 'failed';

-- name: grid
-- Every webhook, with how its last post went.
SELECT w.id, w.name, w.url, w.secret, w.events, array_to_string(w.events, ', ') AS events_text,
       w.format, w.active, w.created_at, last.status AS last_status, last.created_at AS last_at
FROM lattice.webhook w
LEFT JOIN LATERAL (SELECT status, created_at FROM lattice.webhook_delivery d
                   WHERE d.webhook_id = w.id ORDER BY d.id DESC LIMIT 1) last ON true;

-- name: create
-- Add a webhook; returns its id.
INSERT INTO lattice.webhook (name, url, secret, events, format, created_by)
VALUES (:name, :url, :secret, CAST(:events AS text[]), :format, :created_by)
RETURNING id;

-- name: set_active
-- Turn webhooks on or off.
UPDATE lattice.webhook SET active = :active WHERE id = ANY(:ids);

-- name: delete
-- Delete webhooks and their deliveries.
DELETE FROM lattice.webhook WHERE id = ANY(:ids);

-- name: deliveries
-- Every post, with its webhook's name.
SELECT d.id, d.webhook_id, w.name AS webhook, d.event_type, d.subject, d.body, d.status,
       d.attempts, d.response_status, d.last_error, d.created_at, d.delivered_at
FROM lattice.webhook_delivery d JOIN lattice.webhook w ON w.id = d.webhook_id;
