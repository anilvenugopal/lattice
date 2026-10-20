-- Notifications by email (ADR 0016, phase 2): each person's choice per kind, and the
-- queue of emails, sent in the background with retries.

ALTER TABLE lattice.notification ADD COLUMN emailed_at timestamp;

CREATE TABLE lattice.notification_choice (
  user_id bigint       NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  kind    varchar(128) NOT NULL,
  channel varchar(8)   NOT NULL CHECK (channel IN ('app', 'email', 'digest')),
  PRIMARY KEY (user_id, kind)
);

CREATE TABLE lattice.email (
  id               bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id          bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  to_address       varchar(255) NOT NULL,
  subject          varchar(255) NOT NULL,
  body             text         NOT NULL,
  kind             varchar(16)  NOT NULL,            -- notification, digest, test
  notification_ids bigint[]     NOT NULL DEFAULT '{}',
  status           varchar(8)   NOT NULL DEFAULT 'queued',  -- queued, sent, logged, failed
  attempts         integer      NOT NULL DEFAULT 0,
  next_attempt_at  timestamp    NOT NULL DEFAULT lattice.utc_now(),
  last_error       text         NOT NULL DEFAULT '',
  created_at       timestamp    NOT NULL DEFAULT lattice.utc_now(),
  sent_at          timestamp
);
CREATE INDEX email_due ON lattice.email (next_attempt_at) WHERE status = 'queued';
CREATE INDEX email_user ON lattice.email (user_id, kind, created_at);
