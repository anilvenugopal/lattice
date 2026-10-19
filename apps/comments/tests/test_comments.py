"""Comments: a panel on other apps' record pages, by reference, announcing comments.added."""

from pathlib import Path

import pytest

from lattice.api import sql_queries, urn
from lattice.testing import csrf

CHECK = sql_queries(Path(__file__).parent / "sql").checks


@pytest.fixture
def item(db, users):
    return db.value(CHECK.add_item, ref="IT-0901", name="Pump", owner_id=users["viewer"].id)


def comment(client, subject, body):
    return client.post("/comments/add", data={"subject": subject, "body": body},
                       headers={"X-CSRF-Token": csrf(client)})


def test_the_panel_appears_on_the_showcase_item_page(as_user, item):
    html = as_user("viewer").get(f"/showcase/items/{item}").text
    assert 'class="comments"' in html and "No comments yet." in html
    assert 'name="body"' not in html                       # viewers read, editors write
    assert 'name="body"' in as_user("editor").get(f"/showcase/items/{item}").text


def test_a_comment_reaches_the_items_owner(as_user, users, item, db):
    c = as_user("editor")
    res = comment(c, urn("showcase.item", item), "Valve looks worn.")
    assert res.status_code == 200 and "Valve looks worn." in res.text
    [message, *_] = db.all(CHECK.messages_of, owner_id=users["viewer"].id)
    assert message["subject"] == "Editor commented on IT-0901 · Pump"
    assert "Valve looks worn." in message["body"]


def test_commenting_on_your_own_item_sends_no_message(as_user, users, db):
    own = db.value(CHECK.add_item, ref="IT-0902", name="Mine", owner_id=users["editor"].id)
    comment(as_user("editor"), urn("showcase.item", own), "Note to self")
    assert db.all(CHECK.messages_of, owner_id=users["editor"].id) == []


def test_viewers_cannot_comment_and_unknown_records_are_refused(as_user, item):
    assert comment(as_user("viewer"), urn("showcase.item", item), "Hi").status_code == 403
    assert comment(as_user("editor"), urn("showcase.item", 999999), "Hi").status_code == 404


def test_delete_own_or_moderate(as_user, users, item, db):
    subject = urn("showcase.item", item)
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


def test_the_comments_list_draws_each_subject_with_its_owners_resolver(as_user, item):
    comment(as_user("editor"), urn("showcase.item", item), "Listed")
    html = as_user("viewer").get("/_grid/comments.all/rows").text
    assert f'href="/showcase/items/{item}"' in html and "IT-0901 · Pump" in html
    assert "tone-warning" in html                           # the item's status badge
