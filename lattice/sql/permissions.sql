-- Permissions: the ones the database has seen, and which roles have them.

-- name: known
-- Every permission the database has recorded.
SELECT key FROM lattice.permission;

-- name: record
-- Record a permission the code declares for the first time.
INSERT INTO lattice.permission (key) VALUES (:key);

-- name: grant_defaults
-- Grant a new permission to its default roles; roles that do not exist are skipped.
INSERT INTO lattice.role_permission (role_code, permission)
SELECT code, :permission FROM lattice.role WHERE code = ANY(:roles) AND code <> 'admin'
ON CONFLICT DO NOTHING;
