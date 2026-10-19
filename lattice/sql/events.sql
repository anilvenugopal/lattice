-- Event feeds (lattice/kernel/events.py).

-- name: lock_feed
-- Take the feed's lock for this transaction, if no other process holds it.
SELECT pg_try_advisory_xact_lock(hashtext('lattice.event_feed:' || :key));

-- name: cursor
-- The id of the last event delivered from a feed.
SELECT last_id FROM lattice.event_feed WHERE key = :key;

-- name: move_cursor
-- Record the last event delivered from a feed.
INSERT INTO lattice.event_feed (key, last_id) VALUES (:key, :last_id)
ON CONFLICT (key) DO UPDATE SET last_id = EXCLUDED.last_id, updated_at = lattice.utc_now();
