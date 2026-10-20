-- The catastrophe story replaces the sample pages: their tables go. Claims gain a desk
-- handler (a user of this app), and handlers get notices, such as a comment on their claim.

DROP TABLE showcase.item_link, showcase.item, showcase.job, showcase.message;

ALTER TABLE showcase.claim
  ADD COLUMN handler_id bigint REFERENCES lattice.app_user (id) ON DELETE SET NULL;

-- A notice for one user. Only its owner sees it (the grid's query filters on the user).
CREATE TABLE showcase.notice (
  id         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  owner_id   bigint       NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  subject    varchar(255) NOT NULL,
  body       text         NOT NULL DEFAULT '',
  href       varchar(255) NOT NULL DEFAULT '',
  is_read    boolean      NOT NULL DEFAULT false,
  created_at timestamp    NOT NULL DEFAULT lattice.utc_now()
);
CREATE INDEX notice_owner_id ON showcase.notice (owner_id, created_at);
