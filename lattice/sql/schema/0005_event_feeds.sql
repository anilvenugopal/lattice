-- Event feeds (ADR 0011): how far Lattice has read each other system's outbox.

CREATE TABLE lattice.event_feed (
  key        varchar(128) PRIMARY KEY,         -- the EventFeed's key
  last_id    bigint       NOT NULL,            -- the id of the last event delivered
  updated_at timestamp    NOT NULL DEFAULT lattice.utc_now()
);
