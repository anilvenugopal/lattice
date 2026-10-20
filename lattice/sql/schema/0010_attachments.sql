-- Attachments (ADR 0017): files kept with any record, by its URN. The contents are in the
-- file store (LATTICE_FILES_DIR) under `key`; this is what is known about them.

CREATE TABLE lattice.attachment (
  id           bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  subject      varchar(255)  NOT NULL,                 -- the record's URN
  name         varchar(255)  NOT NULL,                 -- as uploaded
  content_type varchar(128)  NOT NULL,
  size         bigint        NOT NULL,
  sha256       varchar(64)   NOT NULL,
  store_key    varchar(255)  NOT NULL UNIQUE,          -- the file's random name in the store
  added_by     bigint        REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  created_at   timestamp     NOT NULL DEFAULT lattice.utc_now()
);
CREATE INDEX attachment_subject ON lattice.attachment (subject, created_at);
