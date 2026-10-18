-- Per-user preferences, one JSON value per key.

-- name: for_user
-- Every preference a user has saved.
SELECT key, value FROM lattice.user_preference WHERE user_id = :user_id;

-- name: save
-- Set one preference. `value` is JSON text.
INSERT INTO lattice.user_preference (user_id, key, value)
VALUES (:user_id, :key, CAST(:value AS jsonb))
ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value;
