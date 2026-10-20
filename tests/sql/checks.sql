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

-- name: role_permissions
-- The permissions granted to one role.
SELECT permission FROM lattice.role_permission WHERE role_code = :role ORDER BY permission;

-- name: take_permission
-- Take a permission away from a role, as an administrator would.
DELETE FROM lattice.role_permission WHERE role_code = :role AND permission = :permission;

-- name: add_role
-- A role made by an administrator.
INSERT INTO lattice.role (code, label) VALUES (:code, :label);

-- name: grant_permission
-- Give a role a permission.
INSERT INTO lattice.role_permission (role_code, permission) VALUES (:role, :permission);

-- name: role
-- One role.
SELECT code, label, description FROM lattice.role WHERE code = :code;

-- name: audit_detail
-- The detail of the latest audit event with this action.
SELECT detail FROM lattice.audit_event WHERE action = :action ORDER BY id DESC LIMIT 1;

-- name: mapped_events
-- Audit events placed on a map for the map tests: each at a made-up point, county and cell.
SELECT id, -95.0 + id * 0.01 AS lon, 29.5 AS lat, action, target_type,
       CAST(target_id AS text) AS county_fips, CAST('87446124cffffff' AS text) AS h3_7,
       CAST(1 AS integer) AS weight
FROM lattice.audit_event
WHERE action LIKE 'maptest.%';

-- name: schema_exists
-- Whether a schema exists.
SELECT count(*) FROM information_schema.schemata WHERE schema_name = :name;
