-- Items: sample records with one column of every kind.

-- name: grid
-- Every item with its owner's name and its parent's reference. The grid adds search,
-- filters, sort and paging.
SELECT i.id, i.ref, i.name, i.category, i.status, i.priority, i.owner_id,
       u.display_name AS owner, i.amount, i.progress, i.score, i.tags, i.starred,
       i.country, i.parent_id, p.ref AS parent_ref, i.due_on, i.created_at, i.updated_at
FROM showcase.item i
LEFT JOIN lattice.app_user u ON u.id = i.owner_id
LEFT JOIN showcase.item p ON p.id = i.parent_id;

-- name: by_id
-- One item, with its notes.
SELECT i.id, i.ref, i.name, i.category, i.status, i.priority, i.owner_id, i.parent_id,
       i.amount, i.progress, i.score, i.tags, i.starred, i.country, i.notes, i.due_on,
       i.created_at, i.updated_at
FROM showcase.item i
WHERE i.id = :id;

-- name: children
-- The items whose parent is one of :ids.
SELECT id, parent_id, ref, name, status FROM showcase.item
WHERE parent_id = ANY(:ids)
ORDER BY ref;

-- name: roots
-- Items that have children but no parent: the tops of the item tree.
SELECT i.id, i.ref, i.name, i.status FROM showcase.item i
WHERE i.parent_id IS NULL AND EXISTS (SELECT 1 FROM showcase.item c WHERE c.parent_id = i.id)
ORDER BY i.ref
LIMIT :limit;

-- name: linked
-- Items that take part in a dependency, for the graph.
SELECT DISTINCT i.id, i.ref, i.name, i.status FROM showcase.item i
JOIN showcase.item_link l ON i.id IN (l.from_id, l.to_id)
ORDER BY i.id;

-- name: links
-- Every dependency between items.
SELECT from_id, to_id FROM showcase.item_link;

-- name: create
-- A new item whose ref comes from its id (IT-0042). Returns the id.
WITH n AS (SELECT nextval(pg_get_serial_sequence('showcase.item', 'id')) AS id)
INSERT INTO showcase.item
  (id, ref, name, category, status, priority, owner_id, amount, due_on, notes)
SELECT n.id, 'IT-' || lpad(CAST(n.id AS text), 4, '0'), :name, :category, :status, :priority,
       :owner_id, :amount, :due_on, :notes
FROM n
RETURNING id;

-- name: update
-- Save an edited item.
UPDATE showcase.item
SET name = :name, category = :category, status = :status, priority = :priority,
    owner_id = :owner_id, amount = :amount, due_on = :due_on, notes = :notes,
    updated_at = lattice.utc_now()
WHERE id = :id;

-- name: assign
-- Give items an owner, or none.
UPDATE showcase.item SET owner_id = :owner_id, updated_at = lattice.utc_now()
WHERE id = ANY(:ids);

-- name: set_status
-- Move items to a status; done items are complete.
UPDATE showcase.item
SET status = CAST(:status AS varchar), updated_at = lattice.utc_now(),
    progress = CASE WHEN CAST(:status AS varchar) = 'done' THEN 100 ELSE progress END
WHERE id = ANY(:ids);

-- name: star
-- Star items that are not starred, and unstar those that are.
UPDATE showcase.item SET starred = NOT starred WHERE id = ANY(:ids);

-- name: delete
-- Delete items.
DELETE FROM showcase.item WHERE id = ANY(:ids);
