"""Showcase grid actions: the home tiles, audit, taking a claim."""

from pathlib import Path

from lattice.api import notifications, sql_queries, urn
from lattice.testing import post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def test_home_tiles_count_only_your_own_rows(as_user, users, claims, db):
    html = as_user("viewer").get("/").text
    assert '<span class="stat__value">1</span><span class="stat__label">My open claims' in html


def test_grid_actions_write_one_audit_event_per_row(as_user, claims, db):
    c = as_user("editor")
    post_json(c, "/_grid/showcase.claims/action/prioritise", {"ids": [claims[0].id, claims[1].id]})
    events = db.all(CHECK.audit_events, action="showcase.claims.prioritise")
    assert len(events) == 2 and len({e["at"] for e in events}) == 1


def test_take_makes_you_the_handler_and_a_follower(as_user, users, claims, db):
    post_json(as_user("editor"), "/_grid/showcase.claims/action/take", {"ids": [claims[4].id]})
    assert db.one(CHECK.claim, id=claims[4].id)["handler_id"] == users["editor"].id
    assert notifications.following(db, users["editor"].id, urn("showcase.claim", claims[4].id))
