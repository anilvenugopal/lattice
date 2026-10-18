"""Demo grid actions: jobs, inbox, work items."""

from pathlib import Path

from lattice.api import sql_queries
from lattice.testing import post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def _jobs(db, *statuses):
    return [db.value(CHECK.add_job, name=f"job {s}", job_type="sync", status=s) for s in statuses]


def test_run_job_creates_a_queued_job(as_user, db):
    c = as_user("viewer")
    resp = post_json(c, "/_grid/demo.jobs/action/new", {"values": {"name": "Nightly", "job_type": "export"}})
    assert resp.status_code == 200
    job = db.one(CHECK.job_by_name, name="Nightly")
    assert job["status"] == "queued" and job["job_type"] == "export"


def test_retry_only_failed_or_cancelled_and_cancel_only_active(as_user, db):
    failed, done, running = _jobs(db, "failed", "succeeded", "running")
    c = as_user("editor")
    body = post_json(c, "/_grid/demo.jobs/action/retry", {"ids": [failed, done]}).json()
    assert "1 skipped" in body["message"]
    body = post_json(c, "/_grid/demo.jobs/action/cancel", {"ids": [running, done]}).json()
    assert "1 skipped" in body["message"]
    retried = db.one(CHECK.job, id=failed)
    assert (retried["status"], retried["attempts"]) == ("queued", 2)
    assert db.one(CHECK.job, id=done)["status"] == "succeeded"
    assert db.one(CHECK.job, id=running)["status"] == "cancelled"


def test_inbox_star_archive_and_move_back(as_user, users, items, db):
    msg = db.value(CHECK.first_message_of, owner_id=users["editor"].id)
    c = as_user("editor")
    post_json(c, "/_grid/demo.inbox/action/star", {"ids": [msg]})
    assert db.one(CHECK.message, id=msg)["is_starred"]
    post_json(c, "/_grid/demo.inbox/action/star", {"ids": [msg]})
    assert not db.one(CHECK.message, id=msg)["is_starred"]
    post_json(c, "/_grid/demo.inbox/action/archive", {"ids": [msg]})
    assert db.one(CHECK.message, id=msg)["folder"] == "archive"
    resp = post_json(c, "/_grid/demo.inbox/action/archive", {"ids": [msg]}).json()
    assert "none of the selected rows qualify" in resp["message"]
    post_json(c, "/_grid/demo.inbox/action/move_inbox", {"ids": [msg]})
    assert db.one(CHECK.message, id=msg)["folder"] == "inbox"


def test_home_unread_tile_counts_only_own_messages(as_user, users, items, db):
    db.value(CHECK.add_message, owner_id=users["viewer"].id, sender_name="X",
             sender_email="x@x.io", subject="s", body="")
    html = as_user("viewer").get("/").text
    assert '<span class="stat__value">2</span><span class="stat__label">Unread messages' in html


def test_grid_actions_write_one_audit_event_per_row(as_user, items, db):
    c = as_user("editor")
    post_json(c, "/_grid/demo.work_items/action/approve", {"ids": [items[0].id, items[1].id]})
    events = db.all(CHECK.audit_events, action="demo.work_items.approve")
    assert len(events) == 2 and len({e["at"] for e in events}) == 1
