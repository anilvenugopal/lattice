"""Catastrophe response pages: events, declaring one, exposure runs, locations and claims."""

import json
from datetime import date
from pathlib import Path

import pytest

import geoengine
from lattice.api import sql_queries
from lattice.testing import csrf, post_json
from lattice_showcase import cat_seed, exposure

CHECK = sql_queries(Path(__file__).parent / "sql").checks


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


def declare(client, counties="Harris", **extra):
    data = {"csrf_token": csrf(client), "data/name": "Hailstorm test", "data/region": "Texas",
            "data/starts_on": "2026-10-19", "data/peril/__variant": "1",
            "data/peril/hail_size_in": "2", "data/footprint/__variant": "0",
            "data/footprint/state": json.dumps("TX"), "data/footprint/counties": counties}
    return client.post("/showcase/events/new", data=data | extra, follow_redirects=False)


def test_declare_an_event_and_run_its_exposure(as_user, book, db):
    c = as_user("editor")
    res = declare(c)
    assert res.status_code == 303, res.text
    event_id = int(res.headers["location"].rsplit("/", 1)[1])
    page = c.get(f"/showcase/events/{event_id}").text
    assert "Hailstorm test" in page and "Queued" in page
    assert exposure.process_next() is True and exposure.process_next() is False
    page = c.get(f"/showcase/events/{event_id}").text
    assert "$1,000,000" in page                         # 100k + 200k + 300k + 400k in Harris
    rows = c.get(f"/_grid/showcase.exposure/rows?x_event_id={event_id}").text
    assert rows.count("<tr data-id") == 4


def test_unknown_counties_are_reported(as_user, book):
    res = declare(as_user("editor"), counties="Harris, Atlantis")
    assert res.status_code == 400 and "No insured locations in: atlantis" in res.text


def test_viewers_cannot_declare(as_user, book):
    assert declare(as_user("viewer")).status_code == 403


def test_a_drawn_shape_narrows_locations_and_can_be_saved(as_user, book, db):
    c = as_user("editor")
    shape = json.dumps(square(-96, 29.5, 0.3))           # the first three Harris locations
    rows = c.get("/_grid/showcase.locations/rows", params={"shape": shape}).text
    assert rows.count("<tr data-id") == 3
    params = "shape=" + json.dumps(square(-96, 29.5, 0.3))
    res = post_json(c, "/_grid/showcase.locations/action/save_area",
                    {"ids": [], "params": params, "values": {"name": "Zone 3"}}).json()
    assert "Saved area 'Zone 3'" in res["message"]
    res = declare(c, **{"data/footprint/__variant": "2", "data/footprint/area": "Zone 3"})
    assert res.status_code == 303
    exposure.process_next()
    event_id = int(res.headers["location"].rsplit("/", 1)[1])
    rows = c.get(f"/_grid/showcase.exposure/rows?x_event_id={event_id}").text
    assert rows.count("<tr data-id") == 3


def test_pages_render(as_user, book):
    c = as_user("viewer")
    for path in ("/showcase/events", "/showcase/locations", "/showcase/claims"):
        assert c.get(path).status_code == 200, path
