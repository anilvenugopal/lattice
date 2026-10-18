-- The audit log: who did what, to which record, and when.

-- name: record
-- One event. Events written in one transaction share their time.
INSERT INTO lattice.audit_event (actor_id, action, summary, target_type, target_id, detail)
VALUES (:actor_id, :action, :summary, :target_type, :target_id, :detail);

-- name: history
-- Newest events about one record and/or by one person, one line per bulk action.
-- With neither given, the newest events of all.
SELECT e.action, e.summary, e.at,
       COALESCE(max(u.display_name), 'System') AS actor
FROM lattice.audit_event e
LEFT JOIN lattice.app_user u ON u.id = e.actor_id
WHERE (CAST(:target_type AS varchar) IS NULL AND CAST(:actor_id AS bigint) IS NULL)
   OR (e.target_type = :target_type AND e.target_id = :target_id)
   OR e.actor_id = :actor_id
GROUP BY e.actor_id, e.action, e.summary, e.at
ORDER BY e.at DESC
LIMIT :limit;

-- name: grid
-- Administration › Audit log: every event with the actor's name.
SELECT e.id, e.at, e.action, e.summary, e.target_type, e.target_id, e.detail,
       COALESCE(u.display_name, 'System') AS actor
FROM lattice.audit_event e
LEFT JOIN lattice.app_user u ON u.id = e.actor_id;

-- name: actions
-- Event names that occur, for the Event filter: (value, label).
SELECT DISTINCT action AS value, action AS label FROM lattice.audit_event ORDER BY action;

-- name: target_types
-- Target types that occur, for the Target filter: (value, label).
SELECT DISTINCT target_type AS value, target_type AS label
FROM lattice.audit_event WHERE target_type <> '' ORDER BY target_type;

-- name: record_many
-- The same event about many records at once (a grid action on its selected rows).
INSERT INTO lattice.audit_event (actor_id, action, summary, target_type, target_id, detail)
SELECT :actor_id, :action, :summary, :target_type, t, :detail
FROM unnest(CAST(:target_ids AS varchar[])) AS t;
