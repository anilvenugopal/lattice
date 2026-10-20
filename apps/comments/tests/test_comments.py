"""Comments: a panel on other apps' record pages, by reference, announcing comments.added."""

from pathlib import Path

import pytest

import geoengine
from lattice.api import sql_queries, urn
from lattice.testing import csrf

CHECK = sql_queries(Path(__file__).parent / "sql").checks


@pytest.fixture
def location(db):
    layer = geoengine.create_layer(db.conn, "locations", "points")
    geoengine.put_points(db.conn, layer, [{"id": "LOC-T1", "lon": -95.4, "lat": 29.7,
                                           "quality": "rooftop"}])
    db.run(CHECK.add_location, ref="LOC-T1")


@pytest.fixture
def claim(db, users, location):
    """A claim the viewer handles."""
    return db.value(CHECK.add_claim, claim_number="CLM-26-T00901", handler_id=users["viewer"].id)


def comment(client, subject, body):
    return client.post("/comments/add", data={"subject": subject, "body": body},
                       headers={"X-CSRF-Token": csrf(client)})


def test_the_panel_appears_on_the_showcase_claim_page(as_user, claim):
    html = as_user("viewer").get(f"/showcase/claims/{claim}").text
    assert 'class="comments"' in html and "No comments yet." in html
    assert 'name="body"' not in html                       # viewers read, editors write
    assert 'name="body"' in as_user("editor").get(f"/showcase/claims/{claim}").text


def test_a_comment_reaches_the_claims_handler(as_user, users, claim, db):
    c = as_user("editor")
    res = comment(c, urn("showcase.claim", claim), "Roof photos attached.")
    assert res.status_code == 200 and "Roof photos attached." in res.text
    [notice, *_] = db.all(CHECK.notices_of, owner_id=users["viewer"].id)
    assert notice["subject"] == "Editor commented on CLM-26-T00901 · Pat Pump"
    assert "Roof photos attached." in notice["body"]


def test_commenting_on_your_own_claim_sends_no_notice(as_user, users, location, db):
    own = db.value(CHECK.add_claim, claim_number="CLM-26-T00902", handler_id=users["editor"].id)
    comment(as_user("editor"), urn("showcase.claim", own), "Note to self")
    assert db.all(CHECK.notices_of, owner_id=users["editor"].id) == []


def test_viewers_cannot_comment_and_unknown_records_are_refused(as_user, claim):
    assert comment(as_user("viewer"), urn("showcase.claim", claim), "Hi").status_code == 403
    assert comment(as_user("editor"), urn("showcase.claim", 999999), "Hi").status_code == 404


def test_delete_own_or_moderate(as_user, users, claim, db):
    subject = urn("showcase.claim", claim)
    comment(as_user("editor"), subject, "First")
    [first] = db.all(CHECK.comments_on, subject=subject)
    c = as_user("editor")
    assert c.post(f"/comments/{first['id']}/delete",
                  headers={"X-CSRF-Token": csrf(c)}).status_code == 200
    assert db.all(CHECK.comments_on, subject=subject) == []
    comment(as_user("admin"), subject, "Admin's")
    [second] = db.all(CHECK.comments_on, subject=subject)
    c = as_user("editor")
    assert c.post(f"/comments/{second['id']}/delete",
                  headers={"X-CSRF-Token": csrf(c)}).status_code == 403


def test_the_comments_list_draws_each_subject_with_its_owners_resolver(as_user, claim):
    comment(as_user("editor"), urn("showcase.claim", claim), "Listed")
    html = as_user("viewer").get("/_grid/comments.all/rows").text
    assert f'href="/showcase/claims/{claim}"' in html and "CLM-26-T00901" in html
    assert "tone-info" in html                              # the claim's status badge
