-- Named places to search by: US cities and towns, counties and zip codes, from the Census
-- gazetteer (refdata/data/us_places.csv.gz, loaded by refdata.migrate).

CREATE TABLE ref.place (
  id    bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind  varchar(8)       NOT NULL,                 -- place, county, zip
  name  varchar(128)     NOT NULL,
  state varchar(2)       NOT NULL DEFAULT '',      -- USPS code; empty for zip codes
  lon   double precision NOT NULL,
  lat   double precision NOT NULL,
  sqmi  real             NOT NULL DEFAULT 0        -- land area: larger places rank first
);
CREATE INDEX place_name ON ref.place (lower(name) text_pattern_ops);
