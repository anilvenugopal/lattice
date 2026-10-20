-- Notices for claim handlers (notices.py).

-- name: grid
-- The current user's notices, and nobody else's: this query is the grid's access boundary.
SELECT id, subject, body, href, is_read, created_at
FROM showcase.notice
WHERE owner_id = :user_id;

-- name: mark_read
-- Mark notices read.
UPDATE showcase.notice SET is_read = true WHERE id = ANY(:ids);

-- name: open
-- Mark one of the user's notices read and return where it points.
UPDATE showcase.notice SET is_read = true
WHERE id = :id AND owner_id = :user_id
RETURNING href;

-- name: add
-- Give one user a notice.
INSERT INTO showcase.notice (owner_id, subject, body, href)
VALUES (:owner_id, :subject, :body, :href);
