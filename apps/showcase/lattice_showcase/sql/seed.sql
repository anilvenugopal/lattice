-- Sample data for `lattice seed`.

-- name: people
-- The users that exist, to own the example rows.
SELECT id FROM lattice.app_user ORDER BY id;

-- name: add_item
-- One sample item.
INSERT INTO showcase.item
  (id, ref, name, category, status, priority, owner_id, parent_id, amount, progress, score,
   tags, starred, country, notes, due_on, created_at, updated_at)
VALUES
  (:id, :ref, :name, :category, :status, :priority, :owner_id, :parent_id, :amount, :progress,
   :score, :tags, :starred, :country, :notes, :due_on, :created_at, :updated_at);

-- name: add_link
-- One dependency between sample items.
INSERT INTO showcase.item_link (from_id, to_id) VALUES (:from_id, :to_id)
ON CONFLICT DO NOTHING;

-- name: sync_item_ids
-- After inserting items with fixed ids, start new ids after them.
SELECT setval(pg_get_serial_sequence('showcase.item', 'id'), (SELECT max(id) FROM showcase.item));

-- name: add_job
-- One example job.
INSERT INTO showcase.job
  (name, job_type, status, submitted_by, created_at, attempts, started_at, finished_at,
   progress, error)
VALUES
  (:name, :job_type, :status, :submitted_by, :created_at, :attempts, :started_at,
   :finished_at, :progress, :error);

-- name: add_message
-- One example message.
INSERT INTO showcase.message
  (owner_id, folder, sender_name, sender_email, subject, body, labels, has_attachment,
   is_read, is_starred, received_at)
VALUES
  (:owner_id, :folder, :sender_name, :sender_email, :subject, :body, :labels,
   :has_attachment, :is_read, :is_starred, :received_at);
