-- The document store (lattice/components/documents.py).

-- name: grid
-- Documents of one kind, for a GridSpec with params={"kind": …}. `data` is the document.
SELECT d.id, d.kind, d.title, d.schema_version, d.data, d.created_at, d.updated_at,
       u.display_name AS updated_by
FROM lattice.document d
LEFT JOIN lattice.app_user u ON u.id = d.updated_by
WHERE d.kind = :kind;

-- name: by_id
-- One document of a kind.
SELECT d.id, d.kind, d.title, d.schema_version, d.data, d.created_at, d.updated_at,
       d.created_by, d.updated_by
FROM lattice.document d
WHERE d.id = :id AND d.kind = :kind;

-- name: of_kind
-- Every document of a kind, newest first.
SELECT d.id, d.title, d.schema_version, d.data, d.updated_at
FROM lattice.document d
WHERE d.kind = :kind
ORDER BY d.updated_at DESC, d.id DESC;

-- name: create
-- Save a new document; returns its id.
INSERT INTO lattice.document (kind, schema_version, title, data, created_by, updated_by)
VALUES (:kind, :schema_version, :title, :data, :user_id, :user_id)
RETURNING id;

-- name: update
-- Replace a document's data.
UPDATE lattice.document
SET data = :data, title = :title, schema_version = :schema_version,
    updated_by = :user_id, updated_at = lattice.utc_now()
WHERE id = :id AND kind = :kind;

-- name: delete
-- Delete documents of a kind.
DELETE FROM lattice.document WHERE id = ANY(:ids) AND kind = :kind;
