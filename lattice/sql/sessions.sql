-- Sign-in sessions. `id` is the SHA-256 of the cookie token, never the token itself.

-- name: create
-- A new session that ends after the absolute limit.
INSERT INTO lattice.user_session (id, user_id, expires_at, ip_address, user_agent, auth_method)
VALUES (:id, :user_id, lattice.utc_now() + make_interval(hours => :max_hours),
        :ip_address, :user_agent, :auth_method);

-- name: signed_in_user
-- The user behind a session that is not revoked, expired, idle too long, or deactivated.
SELECT s.id AS session_id, s.last_seen_at < lattice.utc_now() - interval '60 seconds' AS stale,
       u.id, u.email, u.display_name, u.must_change_password,
       u.password_hash IS NOT NULL AS has_password,
       ARRAY(SELECT r.role_code FROM lattice.user_role r
             WHERE r.user_id = u.id ORDER BY r.role_code) AS roles,
       ARRAY(SELECT DISTINCT p.permission FROM lattice.user_role r
             JOIN lattice.role_permission p ON p.role_code = r.role_code
             WHERE r.user_id = u.id) AS permissions
FROM lattice.user_session s
JOIN lattice.app_user u ON u.id = s.user_id
WHERE s.id = :id
  AND s.revoked_at IS NULL
  AND s.expires_at > lattice.utc_now()
  AND s.last_seen_at > lattice.utc_now() - make_interval(mins => :idle_minutes)
  AND u.is_active;

-- name: touch
-- Record that a session was used.
UPDATE lattice.user_session SET last_seen_at = lattice.utc_now() WHERE id = :id;

-- name: by_id
-- One session's owner and sign-in method.
SELECT id, user_id, auth_method FROM lattice.user_session WHERE id = :id;

-- name: revoke
-- End sessions.
UPDATE lattice.user_session SET revoked_at = lattice.utc_now()
WHERE id = ANY(:ids) AND revoked_at IS NULL;

-- name: revoke_for_users
-- End every session of these users except one (the caller's own, or none).
UPDATE lattice.user_session SET revoked_at = lattice.utc_now()
WHERE user_id = ANY(:user_ids) AND revoked_at IS NULL
  AND id IS DISTINCT FROM CAST(:keep AS varchar);

-- name: active_for_user
-- A user's sessions that are neither revoked nor expired, most recently used first.
SELECT id, auth_method, ip_address, user_agent, created_at, last_seen_at, expires_at
FROM lattice.user_session
WHERE user_id = :user_id AND revoked_at IS NULL AND expires_at > lattice.utc_now()
ORDER BY last_seen_at DESC;

-- name: grid
-- Administration › Sessions: every active session with its user.
SELECT s.id, u.display_name AS user, u.email, s.auth_method, s.ip_address, s.user_agent,
       s.created_at, s.last_seen_at, s.expires_at
FROM lattice.user_session s
JOIN lattice.app_user u ON u.id = s.user_id
WHERE s.revoked_at IS NULL AND s.expires_at > lattice.utc_now();
