-- Roles: named sets of permissions, edited in Administration › Roles.
-- admin, editor and viewer are built in; admin has every permission and is not edited.

-- name: grid
-- Every role with its number of members and permissions.
SELECT r.code AS id, r.label, r.description, r.sort_order,
       r.code IN ('admin', 'editor', 'viewer') AS built_in,
       (SELECT count(*) FROM lattice.user_role m WHERE m.role_code = r.code) AS members,
       CASE WHEN r.code = 'admin' THEN NULL
            ELSE (SELECT count(*) FROM lattice.role_permission p WHERE p.role_code = r.code)
       END AS permissions
FROM lattice.role r;

-- name: by_code
-- One role.
SELECT code, label, description, code IN ('admin', 'editor', 'viewer') AS built_in
FROM lattice.role WHERE code = :code;

-- name: permissions_of
-- The permissions a role has.
SELECT permission FROM lattice.role_permission WHERE role_code = :code ORDER BY permission;

-- name: members
-- The users who have a role.
SELECT u.id, u.display_name, u.email, u.is_active
FROM lattice.user_role r JOIN lattice.app_user u ON u.id = r.user_id
WHERE r.role_code = :code
ORDER BY u.display_name;

-- name: create
-- A new role, listed after the others.
INSERT INTO lattice.role (code, label, description, sort_order)
SELECT :code, :label, :description, COALESCE(max(sort_order), 0) + 1 FROM lattice.role;

-- name: update
-- Change a role's name and description.
UPDATE lattice.role SET label = :label, description = :description WHERE code = :code;

-- name: keep_only_permissions
-- Remove a role's permissions except these.
DELETE FROM lattice.role_permission
WHERE role_code = :code AND NOT (permission = ANY(:permissions));

-- name: add_permissions
-- Give a role these permissions; ones the database has not recorded are skipped.
INSERT INTO lattice.role_permission (role_code, permission)
SELECT :code, key FROM lattice.permission WHERE key = ANY(:permissions)
ON CONFLICT DO NOTHING;

-- name: delete
-- Delete roles that are not built in and have no members.
DELETE FROM lattice.role r
WHERE r.code = ANY(:codes) AND r.code NOT IN ('admin', 'editor', 'viewer')
  AND NOT EXISTS (SELECT 1 FROM lattice.user_role m WHERE m.role_code = r.code);
