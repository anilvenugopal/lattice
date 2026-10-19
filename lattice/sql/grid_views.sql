-- Saved grid views (lattice/components/grid/views.py).

-- name: visible
-- The user's own views of a grid, then views others shared, by name.
SELECT v.id, v.name, v.state, v.shared, v.owner_id = :user_id AS mine,
       u.display_name AS owner_name
FROM lattice.grid_view v
JOIN lattice.app_user u ON u.id = v.owner_id
WHERE v.grid_key = :grid_key AND (v.owner_id = :user_id OR v.shared)
ORDER BY v.owner_id <> :user_id, lower(v.name);

-- name: by_id
-- One view of a grid, if the user may see it.
SELECT v.id, v.name, v.state, v.shared, v.owner_id, v.owner_id = :user_id AS mine
FROM lattice.grid_view v
WHERE v.id = :id AND v.grid_key = :grid_key AND (v.owner_id = :user_id OR v.shared);

-- name: name_taken
-- Whether the user already has another view of this grid with this name.
SELECT EXISTS (SELECT 1 FROM lattice.grid_view
               WHERE grid_key = :grid_key AND owner_id = :user_id
                 AND lower(name) = lower(:name) AND id <> :id);

-- name: create
-- Save a new view; returns its id.
INSERT INTO lattice.grid_view (grid_key, owner_id, name, state, shared)
VALUES (:grid_key, :user_id, :name, :state, :shared)
RETURNING id;

-- name: update
-- Change a view's name, state and sharing.
UPDATE lattice.grid_view
SET name = :name, state = :state, shared = :shared, updated_at = lattice.utc_now()
WHERE id = :id;

-- name: delete
-- Delete one view.
DELETE FROM lattice.grid_view WHERE id = :id;
