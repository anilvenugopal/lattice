-- Notifications (ADR 0016): each person's inbox, and the records people follow.

CREATE TABLE lattice.notification (
  id          bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     bigint        NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  kind        varchar(128)  NOT NULL,                -- a NotificationKind key: "comments.on_followed"
  title       varchar(255)  NOT NULL,
  body        text          NOT NULL DEFAULT '',
  subject     varchar(255)  NOT NULL DEFAULT '',     -- the record's URN, drawn at read time
  actor_id    bigint        REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  count       integer       NOT NULL DEFAULT 1,      -- unread ones about one record collapse
  created_at  timestamp     NOT NULL DEFAULT lattice.utc_now(),
  read_at     timestamp,
  resolved_at timestamp                              -- cleared by the record's closing event
);
CREATE INDEX notification_inbox ON lattice.notification (user_id, created_at DESC, id DESC);
CREATE INDEX notification_subject ON lattice.notification (subject, kind) WHERE read_at IS NULL;

CREATE TABLE lattice.follow (
  user_id    bigint       NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  subject    varchar(255) NOT NULL,
  created_at timestamp    NOT NULL DEFAULT lattice.utc_now(),
  PRIMARY KEY (subject, user_id)
);
CREATE INDEX follow_user ON lattice.follow (user_id);
