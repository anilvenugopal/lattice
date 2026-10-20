-- The exposure snapshot (locations.py).

-- name: grid
-- Every insured location with its point, quality tier and H3 cell.
SELECT l.id, l.ref, l.policy_number, l.insured, l.line, l.occupancy, l.construction,
       l.year_built, l.tiv, l.deductible, l.state, l.county_fips, l.county, l.city,
       p.lon, p.lat, p.quality, p.h3_7
FROM showcase.location l
JOIN geo.point p ON p.layer = 'locations' AND p.external_id = l.ref;
