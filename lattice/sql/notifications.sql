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
RETURNING user_id;

-- name: add
-- New notifications, one per recipient.
INSERT INTO lattice.notification (user_id, kind, title, body, subject, actor_id)
SELECT u, :kind, :title, :body, :subject, :actor_id FROM unnest(CAST(:user_ids AS bigint[])) AS u;

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
