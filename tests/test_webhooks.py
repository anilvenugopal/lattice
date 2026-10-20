"""Webhooks (ADR 0016, phase 3): events posted, signed, retried; administered by admins."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import APIRouter, Depends

from lattice.api import AppManifest, Db, NotificationKind, get_db, sql_queries
from lattice.kernel.services import webhooks
from lattice.testing import csrf, post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks
router = APIRouter()


@router.post("/reply")
def reply(db: Db = Depends(get_db)):
    db.publish("desk.replied", subject="urn:lattice:desk.ticket:7",
               data={"author": "Ann", "author_id": 1, "excerpt": "Done"})


@pytest.fixture
def host_apps():
    return [AppManifest(key="desk", label="Desk", routers=[router], publishes=["desk.replied"],
                        notifications=[NotificationKind("desk.reply", "Reply", event="desk.replied",
                                                        title="{author} replied", body="{excerpt}")])]


def add(c, name, url="https://hooks.example.com/in", events="*", format="cloudevents"):
    return post_json(c, "/_grid/webhooks/action/new", {"ids": [], "values": {
        "name": name, "url": url, "events": events, "format": format}}).json()


def deliveries(db):
    return db.all(CHECK.webhook_deliveries)


def test_addresses_must_be_https_or_local_in_development():
    assert webhooks.check_url("https://hooks.slack.com/x") == "https://hooks.slack.com/x"
    assert webhooks.check_url("http://localhost:9000/in") == "http://localhost:9000/in"
    for bad in ("http://example.com/in", "ftp://example.com", "https://", "nonsense"):
        with pytest.raises(ValueError, match="https://"):
            webhooks.check_url(bad)


def test_an_event_is_queued_for_each_webhook_that_takes_it(as_user, db):
    c = as_user("admin")
    assert "added" in add(c, "Everything")["message"]
    add(c, "Replies to chat", events="desk.replied", format="chat")
    add(c, "Other events", events="comments.added")
    assert "https://" in add(c, "Plain http", url="http://example.com")["message"]
    c.post("/desk/reply", headers={"X-CSRF-Token": csrf(c)})
    by_name = {d["name"]: d for d in deliveries(db)}
    assert set(by_name) == {"Everything", "Replies to chat"}
    event = json.loads(by_name["Everything"]["body"])
    assert (event["type"], event["subject"], event["data"]["excerpt"]) == \
        ("desk.replied", "urn:lattice:desk.ticket:7", "Done")
    assert json.loads(by_name["Replies to chat"]["body"]) == {"text": "[Lattice] Ann replied: Done"}


def test_posts_are_signed_and_retried(as_user, db):
    c = as_user("admin")
    add(c, "Receiver")
    c.post("/desk/reply", headers={"X-CSRF-Token": csrf(c)})
    seen, answers = [], [500, 200]

    def receive(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(answers.pop(0), text="busy" if answers else "ok")
    client = httpx.Client(transport=httpx.MockTransport(receive))
    assert webhooks.send_due(db, client) == 0
    [d] = deliveries(db)
    assert (d["status"], d["attempts"], d["response_status"]) == ("queued", 1, 500)
    assert webhooks.send_due(db, httpx.Client(transport=httpx.MockTransport(receive))) == 0  # waits

    db.run(CHECK.deliveries_due)
    assert webhooks.send_due(db, httpx.Client(transport=httpx.MockTransport(receive))) == 1
    request = seen[-1]
    body = request.content.decode()
    ts = request.headers["X-Lattice-Timestamp"]
    assert request.headers["X-Lattice-Signature"] == webhooks.sign(d["secret"], ts, body)
    assert request.headers["Content-Type"] == "application/cloudevents+json"
    assert deliveries(db)[0]["status"] == "delivered"


def test_only_webhook_managers_reach_the_page_and_test_sends(as_user, db):
    assert as_user("editor").get("/admin/webhooks").status_code == 403
    c = as_user("admin")
    add(c, "Pinged")
    page = c.get("/admin/webhooks").text
    assert "Pinged" in page and "Deliveries" in page
    rows = c.get("/_grid/webhooks/rows").text
    hook_id = rows.split('data-id="')[1].split('"')[0]
    res = post_json(c, "/_grid/webhooks/action/test", {"ids": [hook_id]}).json()
    assert "Test queued to 1" in res["message"]
    assert deliveries(db)[0]["event_type"] == "lattice.webhook_test"
