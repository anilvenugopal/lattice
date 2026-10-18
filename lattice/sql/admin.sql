-- Administration: the users and roles lists, and the System page.

-- name: users_grid
-- Administration › Users: every user with their roles as text.
SELECT u.id, u.display_name, u.email, u.is_active, u.must_change_password,
       COALESCE((SELECT string_agg(r.role_code, ', ' ORDER BY r.role_code)
                 FROM lattice.user_role r WHERE r.user_id = u.id), '') AS roles,
       u.oidc_subject IS NOT NULL AS sso, u.created_at, u.last_login_at
FROM lattice.app_user u;

-- name: counts
-- Totals for the System page.
SELECT (SELECT count(*) FROM lattice.app_user) AS users,
       (SELECT count(*) FROM lattice.user_session
        WHERE revoked_at IS NULL AND expires_at > lattice.utc_now()) AS active_sessions,
       (SELECT count(*) FROM lattice.audit_event) AS audit_events;

-- name: ping
-- The health check: the database answers.
SELECT 1;
