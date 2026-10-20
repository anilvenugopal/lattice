"""The showcase's component pages: overview, charts, specs, free-form, flows, and the seed."""

import json
from pathlib import Path

from lattice.api import documents, sql_queries
from lattice.testing import csrf, post_json
from lattice_showcase import specs
from lattice_showcase.seed import seed

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def test_overview_links_every_page(as_user, items):
    html = as_user("viewer").get("/showcase").text
    for href in ("/showcase/items", "/showcase/charts", "/showcase/specs", "/showcase/freeform",
                 "/showcase/flows", "/showcase/jobs", "/showcase/inbox"):
        assert f'href="{href}' in html


def test_charts_page_and_data(as_user, items):
    c = as_user("viewer")
    html = c.get("/showcase/charts").text
    assert html.count("x-data='ltChart(") == 10
    data = c.get("/_chart/showcase.by_status/data?view=all").json()
    assert sorted(data["categories"]) == ["active", "blocked", "done", "new"]
    assert c.get("/_chart/showcase.by_status/data?view=all&f_status=new").json()["categories"] == ["new"]


def test_specs_create_validate_and_edit(as_user, items, db):
    c = as_user("editor")
    assert 'name="data/source/__variant"' in c.get("/showcase/specs/new").text
    bad = c.post("/showcase/specs/new", data={"csrf_token": csrf(c), "data/name": "ab",
                                              "data/source/__variant": "1",
                                              "data/source/team": "Ops",
                                              "data/source/cost_centre": "nope"})
    assert bad.status_code == 400
    assert "At least 3 characters." in bad.text and "the expected format" in bad.text
    good = c.post("/showcase/specs/new", follow_redirects=False,
                  data={"csrf_token": csrf(c), "data/name": "Widget", "data/version": "2",
                        "data/source/__variant": "1", "data/source/team": "Ops",
                        "data/source/cost_centre": "CC-1234"})
    assert good.status_code == 303
    doc_id = int(good.headers["location"].rsplit("/", 1)[1])
    data = documents.get(db, specs.SPEC, doc_id)["data"]
    assert data["source"] == {"kind": "internal", "team": "Ops", "cost_centre": "CC-1234"}
    assert "Widget" in c.get("/showcase/specs").text or "Widget" in c.get(
        "/_grid/showcase.spec/rows").text


def test_specs_need_the_permission(as_user, items):
    c = as_user("viewer")
    assert c.get("/showcase/specs/new").status_code == 403
    assert c.post("/showcase/specs/new", data={"csrf_token": csrf(c)}).status_code == 403


def test_free_form_infers_and_saves_new_fields(as_user, items, db):
    c = as_user("editor")
    html = c.get("/showcase/freeform").text
    assert 'name="data/budget"' in html and 'name="data/steps/1/name"' in html
    res = c.post("/showcase/freeform", follow_redirects=False,
                 data={"csrf_token": csrf(c), "__mode": "json",
                       "__json": json.dumps({"title": "Mine", "size": 3})})
    assert res.status_code == 303
    assert documents.all_of(db, specs.NOTE)[0]["data"] == {"title": "Mine", "size": 3}


def test_flows_page_shows_stepper_tree_and_graph(as_user, items):
    html = as_user("editor").get("/showcase/flows").text
    assert 'class="stepper' in html and "<lt-graph" in html


def test_graph_node_actions_run_through_the_items_grid(as_user, items, db):
    c = as_user("editor")
    body = post_json(c, "/_grid/showcase.items/action/star", {"ids": [items[0].id]}).json()
    assert "Toggled the star" in body["message"]
    assert db.one(CHECK.item, id=items[0].id)["starred"] is True


def test_seed_fills_every_page(db, users):
    seed(db)
    assert db.value(CHECK.count_items) == 400
    assert db.value(CHECK.count_links) > 15
    assert len(documents.all_of(db, specs.SPEC)) == 2
    assert db.value(CHECK.count_locations) > 40_000
    summary = {r["code"]: (r["status"], r["footprints"]) for r in db.all(CHECK.event_summary)}
    assert summary == {"CAT-2602": ("closed", 1), "CAT-2604": ("closed", 1),
                       "CAT-2608": ("recovery", 2), "CAT-2610": ("response", 3)}
    assert all(r["claims"] > 100 for r in db.all(CHECK.event_summary))
    tiv = [r["tiv"] for r in db.all(CHECK.delta_exposure)]
    assert tiv[1] > tiv[2]              # the forecast moved east, away from Houston
