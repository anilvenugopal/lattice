"""The overview, the components on the claims pages, and the seed."""

from pathlib import Path

from lattice.api import sql_queries
from lattice_showcase.cat_seed import seed

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def test_overview_links_every_page(as_user):
    html = as_user("viewer").get("/showcase").text
    for href in ("/showcase/events", "/showcase/events/new", "/showcase/claims",
                 "/showcase/intake", "/showcase/deployment", "/showcase/field-reports",
                 "/showcase/notices", "/showcase/locations"):
        assert f'href="{href}' in html
    assert "Showcase and production" in html


def test_charts_follow_the_grid_filters(as_user, claims):
    c = as_user("viewer")
    html = c.get("/showcase/claims").text
    assert html.count("x-data='ltChart(") == 4
    data = c.get("/_chart/showcase.claims_estimate/data?view=all").json()
    assert sorted(data["categories"]) == ["major", "minor", "moderate", "total"]
    filtered = c.get("/_chart/showcase.claims_estimate/data?view=all&f_severity=minor").json()
    assert filtered["categories"] == ["minor"]


def test_claim_page_shows_stepper_and_tree(as_user, claims):
    html = as_user("viewer").get(f"/showcase/claims/{claims[1].id}").text
    assert 'class="stepper' in html and "Coverages and payments" in html


def test_seed_fills_every_page(db, users):
    seed(db)
    assert db.value(CHECK.count_locations) > 40_000
    summary = {r["code"]: (r["status"], r["footprints"]) for r in db.all(CHECK.event_summary)}
    assert summary == {"CAT-2602": ("closed", 1), "CAT-2604": ("closed", 1),
                       "CAT-2608": ("recovery", 2), "CAT-2610": ("response", 3)}
    assert all(r["claims"] > 100 for r in db.all(CHECK.event_summary))
    assert db.value(CHECK.count_handled) > 0
    tiv = [r["tiv"] for r in db.all(CHECK.delta_exposure)]
    assert tiv[1] > tiv[2]              # the forecast moved east, away from Houston
