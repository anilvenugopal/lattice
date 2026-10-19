-- Comments on any record of any app. A comment holds only the record's reference (a URN,
-- ADR 0011), never a key into another app's tables.

CREATE TABLE comments.comment (
  id         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  subject    varchar(255) NOT NULL,          -- urn:lattice:{kind}:{id}
  author_id  bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  body       text         NOT NULL,
  created_at timestamp    NOT NULL DEFAULT lattice.utc_now()
);
CREATE INDEX comment_subject ON comments.comment (subject, created_at);
