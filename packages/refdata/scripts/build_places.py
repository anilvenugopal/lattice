"""Build refdata/data/us_places.csv.gz from the US Census gazetteer files.

    python scripts/build_places.py FOLDER

FOLDER holds the unzipped 2024 files from
https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/:
2024_Gaz_place_national.txt, 2024_Gaz_counties_national.txt, 2024_Gaz_zcta_national.txt
(public domain). The output keeps what place search needs: kind, name, state, longitude,
latitude and land area in square miles (to rank larger places first).
"""

from __future__ import annotations

import csv
import gzip
import sys
from pathlib import Path

# Words the Census adds after a place's name ("Houston city", "Katy CDP").
SUFFIXES = {"city", "town", "village", "CDP", "borough", "municipality", "comunidad",
            "zona", "urbana", "and", "(balance)", "consolidated", "government", "metropolitan",
            "unified", "urban", "county"}
OUT = Path(__file__).parents[1] / "refdata" / "data" / "us_places.csv.gz"


def rows(path: Path):
    with path.open(encoding="latin-1") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            yield {k.strip(): v.strip() for k, v in row.items()}


def place_name(name: str) -> str:
    words = name.split()
    while len(words) > 1 and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


def main(folder: Path) -> None:
    out = []
    for r in rows(folder / "2024_Gaz_place_national.txt"):
        out.append(("place", place_name(r["NAME"]), r["USPS"], r["INTPTLONG"], r["INTPTLAT"],
                    round(float(r["ALAND_SQMI"]), 1)))
    for r in rows(folder / "2024_Gaz_counties_national.txt"):
        out.append(("county", r["NAME"], r["USPS"], r["INTPTLONG"], r["INTPTLAT"],
                    round(float(r["ALAND_SQMI"]), 1)))
    for r in rows(folder / "2024_Gaz_zcta_national.txt"):
        out.append(("zip", r["GEOID"], "", r["INTPTLONG"], r["INTPTLAT"],
                    round(float(r["ALAND_SQMI"]), 1)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["kind", "name", "state", "lon", "lat", "sqmi"])
        w.writerows(out)
    print(f"{OUT}: {len(out)} places, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
