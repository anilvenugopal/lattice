-- The document store (ADR 0007): JSON documents of mixed shape, each of a kind an app
-- declares, for configuration, templates and low-volume records. Business entities that
-- are filtered, joined or reported on belong in an app's own tables.

CREATE TABLE lattice.document (
  id             bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind           varchar(128) NOT NULL,                 -- "{app}.{name}", the DocumentKind
  schema_version integer      NOT NULL DEFAULT 1,       -- the kind's schema version when saved
  title          varchar(255) NOT NULL DEFAULT '',      -- from the kind's title template
  data           jsonb        NOT NULL,
  created_by     bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  created_at     timestamp    NOT NULL DEFAULT lattice.utc_now(),
  updated_by     bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  updated_at     timestamp    NOT NULL DEFAULT lattice.utc_now()
);

CREATE INDEX document_kind ON lattice.document (kind, updated_at DESC);
