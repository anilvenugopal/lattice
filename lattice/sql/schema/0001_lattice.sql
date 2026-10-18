-- Lattice's own tables: users, roles, sessions, preferences and the audit log.
-- Timestamps are naive UTC (timestamp without time zone); the browser shows them
-- in the user's time zone.

CREATE TABLE lattice.role (
  code        varchar(32)  PRIMARY KEY,
  label       varchar(64)  NOT NULL,
  description varchar(255) NOT NULL DEFAULT '',
  sort_order  integer      NOT NULL DEFAULT 0
);

INSERT INTO lattice.role (code, label, sort_order, description) VALUES
  ('admin',  'Administrator', 1, 'Everything, plus Administration: users, roles, sessions, audit log.'),
  ('editor', 'Editor',        2, 'Create and change records; run bulk actions.'),
  ('viewer', 'Viewer',        3, 'Read access to every page outside Administration.');

CREATE TABLE lattice.app_user (
  id                   bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email                varchar(255) NOT NULL UNIQUE,
  display_name         varchar(255) NOT NULL,
  password_hash        varchar(255),                 -- NULL for SSO-only accounts
  oidc_subject         varchar(255) UNIQUE,
  is_active            boolean      NOT NULL DEFAULT true,
  must_change_password boolean      NOT NULL DEFAULT false,
  created_at           timestamp    NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
  last_login_at        timestamp
);

CREATE TABLE lattice.user_role (
  user_id   bigint      NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  role_code varchar(32) NOT NULL REFERENCES lattice.role (code),
  PRIMARY KEY (user_id, role_code)
);

-- id is the SHA-256 of the session cookie, never the cookie itself.
CREATE TABLE lattice.user_session (
  id           varchar(64)  PRIMARY KEY,
  user_id      bigint       NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  created_at   timestamp    NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
  last_seen_at timestamp    NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
  expires_at   timestamp    NOT NULL,
  ip_address   varchar(45)  NOT NULL DEFAULT '',
  user_agent   varchar(512) NOT NULL DEFAULT '',
  auth_method  varchar(16)  NOT NULL DEFAULT 'password',
  revoked_at   timestamp
);
CREATE INDEX user_session_user_id ON lattice.user_session (user_id);

CREATE TABLE lattice.user_preference (
  user_id bigint       NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  key     varchar(128) NOT NULL,
  value   jsonb        NOT NULL,
  PRIMARY KEY (user_id, key)
);

CREATE TABLE lattice.audit_event (
  id          bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  at          timestamp    NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
  actor_id    bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  action      varchar(64)  NOT NULL,
  target_type varchar(64)  NOT NULL DEFAULT '',
  target_id   varchar(64)  NOT NULL DEFAULT '',
  summary     varchar(512) NOT NULL DEFAULT '',
  detail      jsonb
);
CREATE INDEX audit_event_at ON lattice.audit_event (at);
CREATE INDEX audit_event_action ON lattice.audit_event (action);
-- A record's history: audit.history(target_type, target_id).
CREATE INDEX audit_event_target ON lattice.audit_event (target_type, target_id, at);
