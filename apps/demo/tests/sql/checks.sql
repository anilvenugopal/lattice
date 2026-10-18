-- Rows the demo's tests create, and queries they use to check results.

-- name: add_work_item
-- A work item for a test. Returns its id.
INSERT INTO demo.work_item (ref, title, account, status, owner_id, amount)
VALUES (:ref, :title, :account, :status, :owner_id, :amount)
RETURNING id;

-- name: add_job
-- A job for a test. Returns its id.
INSERT INTO demo.job (name, job_type, status) VALUES (:name, :job_type, :status)
RETURNING id;

-- name: add_message
-- A message for a test. Returns its id.
INSERT INTO demo.message (owner_id, sender_name, sender_email, subject, body)
VALUES (:owner_id, :sender_name, :sender_email, :subject, :body)
RETURNING id;

-- name: job
-- One job.
SELECT id, name, job_type, status, attempts FROM demo.job WHERE id = :id;

-- name: job_by_name
-- The job with this name.
SELECT id, job_type, status FROM demo.job WHERE name = :name;

-- name: message
-- One message.
SELECT id, folder, is_read, is_starred FROM demo.message WHERE id = :id;

-- name: first_message_of
-- The id of a user's first message.
SELECT id FROM demo.message WHERE owner_id = :owner_id ORDER BY id LIMIT 1;

-- name: work_item
-- One work item.
SELECT id, status, owner_id FROM demo.work_item WHERE id = :id;

-- name: owners_with_status
-- The owner of every work item in a status.
SELECT owner_id FROM demo.work_item WHERE status = :status;

-- name: audit_events
-- Audit events with this action.
SELECT target_id, at FROM lattice.audit_event WHERE action = :action;

-- name: preference
-- One saved preference.
SELECT value FROM lattice.user_preference WHERE user_id = :user_id AND key = :key;
