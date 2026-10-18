-- Work Queue: cases that move through review.

-- name: grid
-- Every work item with its owner's name. The grid adds search, filters, sort and paging.
SELECT w.id, w.ref, w.title, w.account, w.status, w.priority, w.owner_id,
       u.display_name AS owner, w.amount, w.received_at, w.updated_at
FROM demo.work_item w
LEFT JOIN lattice.app_user u ON u.id = w.owner_id;

-- name: by_id
-- One work item with its owner's name.
SELECT w.id, w.ref, w.title, w.account, w.status, w.priority, w.owner_id,
       u.display_name AS owner, w.amount, w.description, w.received_at, w.updated_at
FROM demo.work_item w
LEFT JOIN lattice.app_user u ON u.id = w.owner_id
WHERE w.id = :id;

-- name: create
-- A new work item whose ref comes from its id (WI-00042). Returns the id.
WITH n AS (SELECT nextval(pg_get_serial_sequence('demo.work_item', 'id')) AS id)
INSERT INTO demo.work_item
  (id, ref, title, account, status, priority, owner_id, amount, description)
SELECT n.id, 'WI-' || lpad(n.id::text, 5, '0'), :title, :account, :status, :priority,
       :owner_id, :amount, :description
FROM n
RETURNING id;

-- name: update
-- Save an edited work item.
UPDATE demo.work_item
SET title = :title, account = :account, status = :status, priority = :priority,
    owner_id = :owner_id, amount = :amount, description = :description,
    updated_at = lattice.utc_now()
WHERE id = :id;

-- name: assign
-- Give work items an owner, or none.
UPDATE demo.work_item SET owner_id = :owner_id, updated_at = lattice.utc_now()
WHERE id = ANY(:ids);

-- name: set_status
-- Move work items to a status (approve, decline, review…).
UPDATE demo.work_item SET status = :status, updated_at = lattice.utc_now()
WHERE id = ANY(:ids);

-- name: delete
-- Delete work items.
DELETE FROM demo.work_item WHERE id = ANY(:ids);
