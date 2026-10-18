-- Development data for `lattice seed`.

-- name: people
-- The users that exist, to own the example rows.
SELECT id FROM lattice.app_user ORDER BY id;

-- name: add_work_item
-- One example work item.
INSERT INTO demo.work_item
  (ref, title, account, status, priority, owner_id, amount, description, received_at, updated_at)
VALUES
  (:ref, :title, :account, :status, :priority, :owner_id, :amount, :description,
   :received_at, :updated_at);

-- name: add_job
-- One example job.
INSERT INTO demo.job
  (name, job_type, status, submitted_by, created_at, attempts, started_at, finished_at,
   progress, error)
VALUES
  (:name, :job_type, :status, :submitted_by, :created_at, :attempts, :started_at,
   :finished_at, :progress, :error);

-- name: add_message
-- One example message.
INSERT INTO demo.message
  (owner_id, folder, sender_name, sender_email, subject, body, labels, has_attachment,
   is_read, is_starred, received_at)
VALUES
  (:owner_id, :folder, :sender_name, :sender_email, :subject, :body, :labels,
   :has_attachment, :is_read, :is_starred, :received_at);
