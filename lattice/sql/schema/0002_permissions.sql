-- Permissions (ADR 0009). Which permissions exist comes from the code; this
-- records the ones the database has seen, so a new permission gets its default
-- roles once, and which role has which permission.

CREATE TABLE lattice.permission (
  key           varchar(128) PRIMARY KEY,
  first_seen_at timestamp    NOT NULL DEFAULT lattice.utc_now()
);

-- The admin role is not listed here: it has every permission, always.
CREATE TABLE lattice.role_permission (
  role_code  varchar(32)  NOT NULL REFERENCES lattice.role (code) ON DELETE CASCADE,
  permission varchar(128) NOT NULL REFERENCES lattice.permission (key),
  PRIMARY KEY (role_code, permission)
);
