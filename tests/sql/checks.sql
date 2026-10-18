-- Queries the core tests use to check what Lattice wrote.

-- name: user_emails
-- Every user's email.
SELECT email FROM lattice.app_user;

-- name: sessions_of_user
-- Every session of a user, revoked or not.
SELECT id, revoked_at FROM lattice.user_session WHERE user_id = :user_id;

-- name: session_ids
-- Every stored session id (the hashes of the cookies).
SELECT id FROM lattice.user_session;

-- name: session
-- One session.
SELECT id, revoked_at FROM lattice.user_session WHERE id = :id;

-- name: open_session_of_user
-- A user's session that is not revoked.
SELECT id FROM lattice.user_session WHERE user_id = :user_id AND revoked_at IS NULL LIMIT 1;

-- name: add_session
-- A session for a user, valid for an hour.
INSERT INTO lattice.user_session (id, user_id, expires_at)
VALUES (:id, :user_id, lattice.utc_now() + interval '1 hour');

-- name: audit_actions_for_target
-- The actions recorded about one target id.
SELECT action FROM lattice.audit_event WHERE target_id = :target_id;

-- name: audit_actions
-- Every action in the audit log.
SELECT action FROM lattice.audit_event;

-- name: user_list
-- A minimal grid query for test apps.
SELECT id, email FROM lattice.app_user;

-- name: slow_list
-- A grid query that takes half a second, to test the time limit.
WITH pause AS (SELECT pg_sleep(0.5))
SELECT u.id, u.email FROM lattice.app_user u, pause;

-- name: statement_timeout
-- The time limit in force for the current transaction.
SELECT current_setting('statement_timeout');
