-- Jobs: background job runs.

-- name: grid
-- Every job with the name of who submitted it.
SELECT j.id, j.name, j.job_type, j.status, j.progress, j.attempts, j.error,
       u.display_name AS submitted_by, j.created_at, j.started_at, j.finished_at
FROM showcase.job j
LEFT JOIN lattice.app_user u ON u.id = j.submitted_by;

-- name: create
-- Queue a new job. Returns its id.
INSERT INTO showcase.job (name, job_type, submitted_by) VALUES (:name, :job_type, :submitted_by)
RETURNING id;

-- name: retry
-- Queue failed or cancelled jobs again.
UPDATE showcase.job
SET status = 'queued', progress = 0, error = '', started_at = NULL, finished_at = NULL,
    attempts = attempts + 1
WHERE id = ANY(:ids);

-- name: cancel
-- Cancel queued or running jobs.
UPDATE showcase.job SET status = 'cancelled', finished_at = lattice.utc_now() WHERE id = ANY(:ids);

-- name: advance_running
-- Development only: move running jobs forward. Each gains 5–25% progress, succeeds at
-- 100%, and fails at random (3%) or after running for an hour.
WITH step AS (
  SELECT id, LEAST(100, progress + 5 + floor(random() * 21)::int) AS progress,
         random() < 0.03 OR started_at < lattice.utc_now() - interval '1 hour' AS fails
  FROM showcase.job WHERE status = 'running'
)
UPDATE showcase.job j
SET progress = s.progress,
    status = CASE WHEN s.progress >= 100 THEN 'succeeded' WHEN s.fails THEN 'failed' ELSE 'running' END,
    finished_at = CASE WHEN s.progress >= 100 OR s.fails THEN lattice.utc_now() END,
    error = CASE WHEN s.progress < 100 AND s.fails
                 THEN 'TimeoutError: upstream service did not respond within 30s' ELSE j.error END
FROM step s
WHERE j.id = s.id;

-- name: start_queued
-- Development only: start every queued job.
UPDATE showcase.job SET status = 'running', started_at = lattice.utc_now() WHERE status = 'queued';
