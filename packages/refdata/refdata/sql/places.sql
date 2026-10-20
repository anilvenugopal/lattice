-- Named places (places.py).

-- name: count
-- How many places are loaded.
SELECT count(*) FROM ref.place;

-- name: copy
-- Bulk load, fed rows by COPY.
COPY ref.place (kind, name, state, lon, lat, sqmi) FROM STDIN;

-- name: search
-- Places whose name starts with the text, optionally in one state: an exact name first,
-- then towns before counties before zip codes, larger first.
SELECT kind, name, state, lon, lat
FROM ref.place
WHERE lower(name) LIKE lower(:prefix) || '%' ESCAPE '\'
  AND (:state = '' OR state = upper(:state))
ORDER BY lower(name) = lower(:name) DESC,
         CASE kind WHEN 'place' THEN 0 WHEN 'county' THEN 1 ELSE 2 END,
         sqmi DESC
LIMIT :limit;
