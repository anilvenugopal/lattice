-- Saved grid views: a user's named grid state (search, filters, sort), optionally
-- shared with everyone who can open the grid.

CREATE TABLE lattice.grid_view (
  id         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  grid_key   varchar(128) NOT NULL,
  owner_id   bigint       NOT NULL REFERENCES lattice.app_user (id) ON DELETE CASCADE,
  name       varchar(80)  NOT NULL,
  state      text         NOT NULL,        -- the grid's URL query string, without the page
  shared     boolean      NOT NULL DEFAULT false,
  created_at timestamp    NOT NULL DEFAULT lattice.utc_now(),
  updated_at timestamp    NOT NULL DEFAULT lattice.utc_now(),
  UNIQUE (grid_key, owner_id, name)
);

CREATE INDEX grid_view_grid ON lattice.grid_view (grid_key, owner_id);
