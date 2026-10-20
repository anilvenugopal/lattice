-- Attachments (platform/attachments.py, ADR 0017).

-- name: on_subject
-- A record's attachments, newest first.
SELECT a.id, a.name, a.content_type, a.size, a.created_at, a.added_by, u.display_name AS added_by_name
FROM lattice.attachment a LEFT JOIN lattice.app_user u ON u.id = a.added_by
WHERE a.subject = :subject
ORDER BY a.created_at DESC, a.id DESC;

-- name: add
-- Record an attachment; returns its id.
INSERT INTO lattice.attachment (subject, name, content_type, size, sha256, store_key, added_by)
VALUES (:subject, :name, :content_type, :size, :sha256, :store_key, :added_by)
RETURNING id;

-- name: by_id
-- One attachment.
SELECT id, subject, name, content_type, size, store_key, added_by FROM lattice.attachment WHERE id = :id;

-- name: remove
-- Forget one attachment; returns its file's key.
DELETE FROM lattice.attachment WHERE id = :id RETURNING store_key;

-- name: remove_all
-- Forget every attachment of a record; returns their files' keys.
DELETE FROM lattice.attachment WHERE subject = :subject RETURNING store_key;

-- name: grid
-- Every attachment, for Administration › Attachments.
SELECT a.id, a.subject, a.name, a.content_type, a.size, a.created_at, u.display_name AS added_by_name
FROM lattice.attachment a LEFT JOIN lattice.app_user u ON u.id = a.added_by;
