-- Rows the Comments tests create, and queries they use to check results.

-- name: add_item
-- A showcase item to comment on. Returns its id.
INSERT INTO showcase.item (ref, name, status, owner_id) VALUES (:ref, :name, 'active', :owner_id)
RETURNING id;

-- name: messages_of
-- A user's showcase messages, newest first.
SELECT subject, body FROM showcase.message WHERE owner_id = :owner_id ORDER BY id DESC;

-- name: comments_on
-- The comments on one record.
SELECT id, body, author_id FROM comments.comment WHERE subject = :subject ORDER BY id;
