"""Catastrophe response pages: events, declaring one, exposure runs, locations and claims."""

import json
from pathlib import Path

from lattice.api import sql_queries
from lattice.testing import csrf, post_json
from lattice_showcase import exposure

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def square(lon, lat, size=0.5):
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size],
                                                [lon, lat + size], [lon, lat]]]}


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


def live_event(c, db):
    """Declare an event over Harris, run its exposure and move it to landfall."""
    event_id = int(declare(c).headers["location"].rsplit("/", 1)[1])
    exposure.process_next()
    post_json(c, "/_grid/showcase.events/action/advance", {"ids": [event_id]})
    return event_id


def test_intake_claims_handling_assessment_and_reports(as_user, book, db):
    import random

    from lattice_showcase import claims, deployment
    c = as_user("editor")
    event_id = live_event(c, db)
    zone = db.value(CHECK.add_zone, event_id=event_id, name="Houston")
    surveyor = db.value(CHECK.add_surveyor, name="Pat Field")

    # The simulator adds claims only while running.
    assert claims.simulate_intake(random.Random(1), 60) == 0
    post_json(c, "/_grid/showcase.intake/action/start", {"ids": [], "values": {"per_minute": "120"}})
    assert claims.simulate_intake(random.Random(1), 60) == 4      # only 4 exposed, none claimed yet
    made = db.all(CHECK.claims_of, event_id=event_id)
    assert {r["status"] for r in made} == {"new"} and {r["zone_id"] for r in made} == {zone}
    post_json(c, "/_grid/showcase.intake/action/pause", {"ids": []})

    # Assign a surveyor in bulk; the claims become assigned.
    ids = [r["id"] for r in made]
    post_json(c, "/_grid/showcase.claims/action/assign_surveyor",
              {"ids": ids, "values": {"surveyor_id": str(surveyor)}})
    assert {r["status"] for r in db.all(CHECK.claims_of, event_id=event_id)} == {"assigned"}

    # The claim page, then an assessment, which records the inspection.
    first = ids[0]
    assert "Not assessed yet." in c.get(f"/showcase/claims/{first}").text
    form = c.get(f"/showcase/claims/{first}/assessment").text
    assert 'name="data/property/roof"' in form                  # a homeowners claim: the home form
    res = c.post(f"/showcase/claims/{first}/assessment", follow_redirects=False, data={
        "csrf_token": csrf(c), "data/claim_number": made[0]["claim_number"],
        "data/property/__variant": "0", "data/property/roof": json.dumps("major"),
        "data/damage_estimate": "45000", "data/photos": "12", "data/notes": "Roof decking exposed."})
    assert res.status_code == 303, res.text
    page = c.get(f"/showcase/claims/{first}").text
    assert "$45,000" in page and "Roof decking exposed." in page
    assert db.all(CHECK.claims_of, event_id=event_id)[0]["status"] == "inspected"

    # A free-form field report, with a field the template didn't have.
    res = c.post(f"/showcase/claims/{first}/report", follow_redirects=False, data={
        "csrf_token": csrf(c), "__mode": "json",
        "__json": json.dumps({"summary": "Gate locked", "observed": "No access.", "dog": True})})
    assert res.status_code == 303
    assert "Gate locked" in c.get("/_grid/showcase.field_report/rows").text

    # The deployment graph shows the zone and the surveyor.
    graph = c.get("/showcase/deployment").text
    assert "Pat Field" in graph and "Houston" in graph
    assert deployment.ZONES.key in graph or "/_grid/showcase.zones" in graph
    # A surveyor's node opens Claims narrowed to their claims in the zone.
    assert "x_zone=Houston" in graph and "x_surveyor=Pat+Field" in graph
    rows = c.get("/_grid/showcase.claims/rows", params={"view": "all", "x_zone": "Houston",
                                                        "x_surveyor": "Pat Field"}).text
    assert rows.count("<tr data-id") == len(ids)
    assert c.get("/_grid/showcase.claims/rows?view=all&q=Field").text.count("<tr data-id") == len(ids)


def test_claims_pages_render(as_user, book, db):
    c = as_user("viewer")
    for path in ("/showcase/claims", "/showcase/intake", "/showcase/deployment",
                 "/showcase/field-reports", "/showcase/claims-system/CLM-26-000001"):
        assert c.get(path).status_code == 200, path
    assert c.get("/showcase/claims/1/assessment").status_code == 403    # viewers read only


def test_the_loss_model():
    import numpy as np

    from lattice_showcase import losses
    homes = [{"lon": -95.0, "lat": 29.5 + i * 0.5, "tiv": 300_000, "deductible": 2_000,
              "construction": "frame"} for i in range(4)]
    track = np.array([[-95.0, 28.0], [-95.0, 32.0]])
    near = losses.simulate(homes, track, 130, 200, seed=1)
    far = losses.simulate(homes, track + [0.5, 0], 130, 200, seed=1)    # about 50 km away
    assert near.mean() > far.mean() > 0
    assert losses.simulate(homes, track, 30, 50, seed=1).max() == 0      # too weak to damage
    figures = losses.summary(near)
    assert figures["mean_loss"] <= figures["p99_loss"] <= figures["p996_loss"]


def test_run_an_estimate(as_user, book, db):
    from lattice_showcase import losses
    c = as_user("editor")
    event_id = int(declare(c).headers["location"].rsplit("/", 1)[1])
    exposure.process_next()
    assert "Run one" in c.get(f"/showcase/events/{event_id}/loss").text
    res = post_json(c, "/_grid/showcase.loss_runs/action/run",
                    {"ids": [], "params": f"x_event_id={event_id}", "values": {"simulations": "500"}})
    assert "queued" in res.json()["message"]
    assert losses.process_next() is True
    page = c.get(f"/showcase/events/{event_id}/loss").text
    assert "1 in 100" in page and "Illustrative" in page
    curve = c.get(f"/_chart/showcase.loss_exceedance/data?x_event_id={event_id}").json()
    assert curve["points"][0][2] == 100 and len(curve["points"]) == 201
