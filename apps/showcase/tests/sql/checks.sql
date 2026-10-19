-- Rows the showcase's tests create, and queries they use to check results.

-- name: add_item
-- An item for a test. Returns its id.
INSERT INTO showcase.item (ref, name, category, status, owner_id, amount)
VALUES (:ref, :name, :category, :status, :owner_id, :amount)
RETURNING id;

-- name: add_job
-- A job for a test. Returns its id.
INSERT INTO showcase.job (name, job_type, status) VALUES (:name, :job_type, :status)
RETURNING id;

-- name: add_message
-- A message for a test. Returns its id.
INSERT INTO showcase.message (owner_id, sender_name, sender_email, subject, body)
VALUES (:owner_id, :sender_name, :sender_email, :subject, :body)
RETURNING id;

-- name: job
-- One job.
SELECT id, name, job_type, status, attempts FROM showcase.job WHERE id = :id;

-- name: job_by_name
-- The job with this name.
SELECT id, job_type, status FROM showcase.job WHERE name = :name;

-- name: message
-- One message.
SELECT id, folder, is_read, is_starred FROM showcase.message WHERE id = :id;

-- name: first_message_of
-- The id of a user's first message.
SELECT id FROM showcase.message WHERE owner_id = :owner_id ORDER BY id LIMIT 1;

-- name: item
-- One item.
SELECT id, status, owner_id, starred FROM showcase.item WHERE id = :id;

-- name: owners_with_status
-- The owner of every item in a status.
SELECT owner_id FROM showcase.item WHERE status = :status;

-- name: audit_events
-- Audit events with this action.
SELECT target_id, at FROM lattice.audit_event WHERE action = :action;

-- name: preference
-- One saved preference.
SELECT value FROM lattice.user_preference WHERE user_id = :user_id AND key = :key;

-- name: count_items
-- How many items exist.
SELECT count(*) FROM showcase.item;

-- name: count_links
-- How many item dependencies exist.
SELECT count(*) FROM showcase.item_link;
