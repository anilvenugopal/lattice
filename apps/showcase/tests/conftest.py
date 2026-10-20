"""The showcase's test data: a small book of insured locations, an event and its claims."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

import geoengine
import lattice_showcase
from lattice.api import sql_queries
from lattice_showcase import cat_seed

CHECK = sql_queries(Path(__file__).parent / "sql").checks


@dataclass(frozen=True)
class Claim:
    id: int
    number: str


@pytest.fixture
def host_apps():
    return [lattice_showcase.APP]


def square(lon, lat, size=0.5):
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size],
                                                [lon, lat + size], [lon, lat]]]}


@pytest.fixture
def book(db, users):
    """Two counties (Harris and Galveston, as squares) and six locations."""
    counties = geoengine.create_layer(db.conn, "us-counties", "areas")
    geoengine.put_geojson(db.conn, counties, {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "48201", "properties": {"name": "Harris"}, "geometry": square(-96, 29.5)},
        {"type": "Feature", "id": "48167", "properties": {"name": "Galveston"}, "geometry": square(-95, 29)}]})
    places = geoengine.create_layer(db.conn, "locations", "points")
    points = [(f"LOC-00000{i}", -95.8 + i * 0.05, 29.7, "48201", "Harris") for i in range(4)]
    points += [(f"LOC-00000{i}", -94.8, 29.2 + (i - 4) * 0.05, "48167", "Galveston") for i in (4, 5)]
    geoengine.put_points(db.conn, places, [{"id": ref, "lon": lon, "lat": lat, "quality": "rooftop"}
                                           for ref, lon, lat, _, _ in points])
    db.run_many(cat_seed.SQL.add_location, [
        {"ref": ref, "policy_number": f"HO-{i}", "insured": f"Insured {i}", "line": "homeowners",
         "occupancy": "single_family", "construction": "frame", "year_built": 2000,
         "tiv": 100_000 * (i + 1), "deductible": 1000, "state": "TX", "county_fips": fips,
         "county": county, "city": "Houston", "snapshot_on": date(2026, 10, 19)}
        for i, (ref, _, _, fips, county) in enumerate(points)])


@pytest.fixture
def claims(db, users, book):
    """Six claims on the book: four on a live event, two on a closed one.

    | # | status    | severity | handler | event  |
    |---|-----------|----------|---------|--------|
    | 1 | new       | minor    | editor  | live   |
    | 2 | assigned  | moderate | editor  | live   |
    | 3 | inspected | major    | viewer  | live   |
    | 4 | settled   | total    | -       | live   |
    | 5 | new       | minor    | -       | closed |
    | 6 | closed    | moderate | admin   | closed |
    """
    live = db.value(CHECK.add_event, code="CAT-T01", name="Test hurricane", status="response")
    closed = db.value(CHECK.add_event, code="CAT-T02", name="Old storm", status="closed")
    rows = [("new", "minor", "editor", live), ("assigned", "moderate", "editor", live),
            ("inspected", "major", "viewer", live), ("settled", "total", None, live),
            ("new", "minor", None, closed), ("closed", "moderate", "admin", closed)]
    made = []
    for i, (status, severity, handler, event_id) in enumerate(rows):
        number = f"CLM-26-T{i + 1:05d}"
        made.append(Claim(db.value(
            CHECK.add_claim, claim_number=number, event_id=event_id, location_ref=f"LOC-00000{i}",
            severity=severity, status=status, estimate=(i + 1) * 1000,
            handler_id=users[handler].id if handler else None), number))
    return made
