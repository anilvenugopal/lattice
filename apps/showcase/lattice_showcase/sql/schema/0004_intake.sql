-- The live intake simulator's controls (one row): whether new claims arrive for the live
-- event, and how many a minute. Simulated, and said so on screen.

CREATE TABLE showcase.intake (
  id         integer   PRIMARY KEY CHECK (id = 1),
  running    boolean   NOT NULL DEFAULT false,
  per_minute integer   NOT NULL DEFAULT 30,
  updated_at timestamp NOT NULL DEFAULT lattice.utc_now()
);
INSERT INTO showcase.intake (id) VALUES (1);
