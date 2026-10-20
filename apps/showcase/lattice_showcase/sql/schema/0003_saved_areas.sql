-- Areas users drew on a map and kept ("Evacuation zone 3"), each a geoengine layer, usable as
-- an event's footprint.

CREATE TABLE showcase.area (
  id         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name       varchar(128) NOT NULL UNIQUE,
  layer      varchar(128) NOT NULL,                          -- geo.layer.key
  created_by bigint       REFERENCES lattice.app_user (id) ON DELETE SET NULL,
  created_at timestamp    NOT NULL DEFAULT lattice.utc_now()
);
