-- Notifications and follows (kernel/services/notifications.py, ADR 0016).

-- name: grid
-- The signed-in user's notifications, and nobody else's: the access boundary.
SELECT n.id, n.kind, n.title, n.body, n.subject, n.count, n.created_at, n.read_at,
       n.resolved_at, n.read_at IS NOT NULL OR n.resolved_at IS NOT NULL AS done,
       a.display_name AS actor
FROM lattice.notification n
LEFT JOIN lattice.app_user a ON a.id = n.actor_id
WHERE n.user_id = :user_id;

-- name: collapse
-- Fold a new notification into the recipient's unread one about the same record and kind;
-- returns the users it was folded for.
UPDATE lattice.notification
SET count = count + 1, title = :title, body = :body, actor_id = :actor_id,
    created_at = lattice.utc_now()
WHERE user_id = ANY(:user_ids) AND kind = :kind AND subject = :subject AND subject <> ''
  AND read_at IS NULL AND resolved_at IS NULL
RETURNING id, user_id;

-- name: add
-- New notifications, one per recipient.
INSERT INTO lattice.notification (user_id, kind, title, body, subject, actor_id)
SELECT u, :kind, :title, :body, :subject, :actor_id FROM unnest(CAST(:user_ids AS bigint[])) AS u
RETURNING id;

-- name: resolve
-- Clear open notifications of these kinds about a record.
UPDATE lattice.notification SET resolved_at = lattice.utc_now()
WHERE subject = :subject AND kind = ANY(:kinds) AND resolved_at IS NULL AND read_at IS NULL;

-- name: mark_read
-- Mark some of a user's notifications read.
UPDATE lattice.notification SET read_at = lattice.utc_now()
WHERE id = ANY(:ids) AND user_id = :user_id AND read_at IS NULL;

-- name: mark_all_read
-- Mark all of a user's notifications read.
UPDATE lattice.notification SET read_at = lattice.utc_now()
WHERE user_id = :user_id AND read_at IS NULL AND resolved_at IS NULL;

-- name: open
-- Mark one of a user's notifications read and return what it is about.
UPDATE lattice.notification SET read_at = coalesce(read_at, lattice.utc_now())
WHERE id = :id AND user_id = :user_id
RETURNING subject;

-- name: dismiss
-- Delete some of a user's notifications.
DELETE FROM lattice.notification WHERE id = ANY(:ids) AND user_id = :user_id;

-- name: unread
-- How many notifications a user has not read.
SELECT count(*) FROM lattice.notification
WHERE user_id = :user_id AND read_at IS NULL AND resolved_at IS NULL;

-- name: expire
-- Delete notifications older than the retention period.
DELETE FROM lattice.notification WHERE created_at < lattice.utc_now() - make_interval(days => :days);

-- name: follow_many
-- Make several users follow a record.
INSERT INTO lattice.follow (user_id, subject)
SELECT u, :subject FROM unnest(CAST(:user_ids AS bigint[])) AS u ON CONFLICT DO NOTHING;

-- name: unfollow
-- Stop following a record.
DELETE FROM lattice.follow WHERE user_id = :user_id AND subject = :subject;

-- name: following
-- Whether a user follows a record.
SELECT EXISTS (SELECT 1 FROM lattice.follow WHERE user_id = :user_id AND subject = :subject);

-- name: followers
-- Who follows a record (active users only).
SELECT f.user_id FROM lattice.follow f JOIN lattice.app_user u ON u.id = f.user_id
WHERE f.subject = :subject AND u.is_active;

-- name: email_recipients
-- Of these notifications, those whose recipient chose email for its kind (else the kind's
-- default) and have none already waiting to go.
SELECT n.id, n.user_id, u.email, n.title
FROM lattice.notification n
JOIN lattice.app_user u ON u.id = n.user_id AND u.is_active
LEFT JOIN lattice.notification_choice c ON c.user_id = n.user_id AND c.kind = n.kind
WHERE n.id = ANY(:ids) AND coalesce(c.channel, :default_channel) = 'email'
  AND NOT EXISTS (SELECT 1 FROM lattice.email e
                  WHERE e.status = 'queued' AND n.id = ANY(e.notification_ids));

-- name: queue_email
-- Queue one email.
INSERT INTO lattice.email (user_id, to_address, subject, body, kind, notification_ids)
VALUES (:user_id, :to_address, :subject, :body, :kind, CAST(:ids AS bigint[]));

-- name: digest_due
-- Unread notifications not yet emailed, of kinds their recipient takes as a daily summary,
-- for people who have had no summary in the last 20 hours.
SELECT n.id, n.user_id, u.email, n.title, n.count, n.created_at
FROM lattice.notification n
JOIN lattice.app_user u ON u.id = n.user_id AND u.is_active
LEFT JOIN lattice.notification_choice c ON c.user_id = n.user_id AND c.kind = n.kind
WHERE n.read_at IS NULL AND n.resolved_at IS NULL AND n.emailed_at IS NULL
  AND coalesce(c.channel, CASE WHEN n.kind = ANY(:digest_kinds) THEN 'digest' ELSE 'app' END) = 'digest'
  AND NOT EXISTS (SELECT 1 FROM lattice.email e WHERE e.user_id = n.user_id AND e.kind = 'digest'
                  AND e.created_at > lattice.utc_now() - interval '20 hours')
ORDER BY n.user_id, n.created_at DESC;



-- name: due_emails
-- Queued emails due now, taken by this sender alone.
SELECT id, to_address, subject, body, attempts, notification_ids FROM lattice.email
WHERE status = 'queued' AND next_attempt_at <= lattice.utc_now()
ORDER BY next_attempt_at LIMIT 50
FOR UPDATE SKIP LOCKED;

-- name: email_done
-- Record an email sent (or logged, with no mail server), and its notifications as emailed.
WITH done AS (
  UPDATE lattice.email SET status = :status, sent_at = lattice.utc_now(),
         attempts = attempts + 1, last_error = ''
  WHERE id = :id RETURNING notification_ids)
UPDATE lattice.notification n SET emailed_at = lattice.utc_now()
FROM done WHERE n.id = ANY(done.notification_ids);

-- name: email_failed
-- Record a failed attempt: try again later, or give up after five.
UPDATE lattice.email
SET attempts = attempts + 1, last_error = :error,
    status = CASE WHEN attempts + 1 >= 5 THEN 'failed' ELSE 'queued' END,
    next_attempt_at = lattice.utc_now() + make_interval(mins => CAST(power(2, attempts + 1) AS integer))
WHERE id = :id;

-- name: retry_emails
-- Queue failed emails again.
UPDATE lattice.email SET status = 'queued', attempts = 0, next_attempt_at = lattice.utc_now()
WHERE id = ANY(:ids) AND status = 'failed';

-- name: emails
-- Every email Lattice has queued, sent or logged, for Administration › Email.
SELECT e.id, e.to_address, e.subject, e.body, e.kind, e.status, e.attempts, e.last_error,
       e.created_at, e.sent_at, u.display_name AS recipient
FROM lattice.email e LEFT JOIN lattice.app_user u ON u.id = e.user_id;

-- name: choices
-- A person's chosen channel per kind.
SELECT kind, channel FROM lattice.notification_choice WHERE user_id = :user_id;

-- name: choose
-- Set a person's channel for one kind.
INSERT INTO lattice.notification_choice (user_id, kind, channel) VALUES (:user_id, :kind, :channel)
ON CONFLICT (user_id, kind) DO UPDATE SET channel = excluded.channel;
