-- Users and their roles. Emails are stored lower-case.

-- name: by_email
-- The user with this email, with their role codes.
SELECT u.id, u.email, u.display_name, u.password_hash, u.oidc_subject, u.is_active,
       u.must_change_password, u.created_at, u.last_login_at,
       ARRAY(SELECT r.role_code FROM lattice.user_role r
             WHERE r.user_id = u.id ORDER BY r.role_code) AS roles
FROM lattice.app_user u
WHERE u.email = lower(:email);

-- name: by_id
-- The user with this id, with their role codes.
SELECT u.id, u.email, u.display_name, u.password_hash, u.oidc_subject, u.is_active,
       u.must_change_password, u.created_at, u.last_login_at,
       ARRAY(SELECT r.role_code FROM lattice.user_role r
             WHERE r.user_id = u.id ORDER BY r.role_code) AS roles
FROM lattice.app_user u
WHERE u.id = :id;

-- name: by_oidc_subject
-- The user linked to this single sign-on identity.
SELECT u.id, u.email, u.is_active
FROM lattice.app_user u
WHERE u.oidc_subject = :subject;

-- name: any_exist
-- Whether the database has any users yet.
SELECT EXISTS (SELECT 1 FROM lattice.app_user);

-- name: options
-- Active users as choices for selects and filters: (value, label).
SELECT CAST(id AS text) AS value, display_name AS label
FROM lattice.app_user
WHERE is_active
ORDER BY display_name;

-- name: create
-- A new user. Returns its id.
INSERT INTO lattice.app_user
  (email, display_name, password_hash, must_change_password, oidc_subject, is_active)
VALUES
  (lower(:email), :display_name, :password_hash, :must_change_password, :oidc_subject, :is_active)
RETURNING id;

-- name: rename
-- Change a user's display name.
UPDATE lattice.app_user SET display_name = :display_name WHERE id = :id;

-- name: set_password
-- Set a password hash, and whether it must be changed at the next sign-in.
UPDATE lattice.app_user
SET password_hash = :password_hash, must_change_password = :must_change
WHERE id = :id;

-- name: set_active
-- Activate or deactivate users.
UPDATE lattice.app_user SET is_active = :active WHERE id = ANY(:ids);

-- name: link_oidc
-- Link a single sign-on identity to an existing account.
UPDATE lattice.app_user SET oidc_subject = :subject WHERE id = :id;

-- name: signed_in
-- Record a successful sign-in.
UPDATE lattice.app_user SET last_login_at = lattice.utc_now() WHERE id = :id;

-- name: role_options
-- Every role as (code, label), in display order.
SELECT code, label FROM lattice.role ORDER BY sort_order, code;

-- name: grant_role
-- Give a role to users who do not have it yet; the row count is the number granted.
INSERT INTO lattice.user_role (user_id, role_code)
SELECT u.id, r.code
FROM lattice.app_user u, lattice.role r
WHERE u.id = ANY(:ids) AND r.code = :role
ON CONFLICT DO NOTHING;

-- name: add_roles
-- Give a user these roles; codes that are not roles, or that the user has, are skipped.
INSERT INTO lattice.user_role (user_id, role_code)
SELECT :user_id, code FROM lattice.role WHERE code = ANY(:roles)
ON CONFLICT DO NOTHING;

-- name: remove_role
-- Take a role away from users.
DELETE FROM lattice.user_role WHERE role_code = :role AND user_id = ANY(:ids);

-- name: keep_only_roles
-- Remove every role of a user except these.
DELETE FROM lattice.user_role WHERE user_id = :user_id AND NOT (role_code = ANY(:roles));
