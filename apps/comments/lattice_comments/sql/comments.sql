-- Comments.

-- name: on_subject
-- The comments on one record, oldest first, with their authors' names.
SELECT c.id, c.body, c.created_at, c.author_id, u.display_name AS author
FROM comments.comment c
LEFT JOIN lattice.app_user u ON u.id = c.author_id
WHERE c.subject = :subject
ORDER BY c.created_at, c.id;

-- name: grid
-- Every comment, for the Comments list.
SELECT c.id, c.subject, split_part(c.subject, ':', 3) AS kind, c.body, c.created_at,
       c.author_id, u.display_name AS author
FROM comments.comment c
LEFT JOIN lattice.app_user u ON u.id = c.author_id;

-- name: add
-- Save a comment; returns its id.
INSERT INTO comments.comment (subject, author_id, body) VALUES (:subject, :author_id, :body)
RETURNING id;

-- name: by_id
-- One comment.
SELECT id, subject, author_id FROM comments.comment WHERE id = :id;

-- name: delete
-- Delete comments.
DELETE FROM comments.comment WHERE id = ANY(:ids);
