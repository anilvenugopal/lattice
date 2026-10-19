-- Inbox: each user's own messages.

-- name: grid
-- The signed-in user's messages, with the start of each body as a snippet.
SELECT m.id, m.is_starred, m.sender_name, m.sender_email, m.subject,
       substr(m.body, 1, 160) AS snippet, m.labels, m.has_attachment, m.is_read,
       m.folder, m.received_at
FROM showcase.message m
WHERE m.owner_id = :user_id;

-- name: by_id
-- One message, for the reading pane.
SELECT id, sender_name, sender_email, subject, body, labels, has_attachment, is_read,
       received_at
FROM showcase.message
WHERE id = :id;

-- name: set_read
-- Mark messages read or unread.
UPDATE showcase.message SET is_read = :is_read WHERE id = ANY(:ids);

-- name: set_starred
-- Star or unstar messages.
UPDATE showcase.message SET is_starred = :is_starred WHERE id = ANY(:ids);

-- name: move
-- Move messages to a folder (inbox or archive).
UPDATE showcase.message SET folder = :folder WHERE id = ANY(:ids);

-- name: delete
-- Delete messages.
DELETE FROM showcase.message WHERE id = ANY(:ids);

-- name: notify
-- Put a message in one user's inbox, from Lattice itself.
INSERT INTO showcase.message (owner_id, sender_name, sender_email, subject, body)
VALUES (:owner_id, :sender_name, 'notifications@lattice.local', :subject, :body);
