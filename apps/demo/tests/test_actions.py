"""Demo grid actions: jobs, inbox, work items."""

from sqlalchemy import select

from lattice.kernel.models import AuditEvent
from lattice.testing import post_json
from lattice_demo.models import Job, Message


def _jobs(db, *statuses):
    rows = [Job(name=f"job {s}", job_type="sync", status=s) for s in statuses]
    db.add_all(rows)
    db.commit()
    return rows


def test_run_job_creates_a_queued_job(as_user, db):
    c = as_user("viewer")
    resp = post_json(c, "/_grid/demo.jobs/action/new", {"values": {"name": "Nightly", "job_type": "export"}})
    assert resp.status_code == 200
    job = db.scalar(select(Job).where(Job.name == "Nightly"))
    assert job.status == "queued" and job.job_type == "export"


def test_retry_only_failed_or_cancelled_and_cancel_only_active(as_user, db):
    failed, done, running = _jobs(db, "failed", "succeeded", "running")
    c = as_user("editor")
    body = post_json(c, "/_grid/demo.jobs/action/retry", {"ids": [failed.id, done.id]}).json()
    assert "1 skipped" in body["message"]
    body = post_json(c, "/_grid/demo.jobs/action/cancel", {"ids": [running.id, done.id]}).json()
    assert "1 skipped" in body["message"]
    db.expire_all()
    assert (db.get(Job, failed.id).status, db.get(Job, failed.id).attempts) == ("queued", 2)
    assert db.get(Job, done.id).status == "succeeded"
    assert db.get(Job, running.id).status == "cancelled"


def test_inbox_star_archive_and_move_back(as_user, users, items, db):
    msg = db.scalar(select(Message).where(Message.owner_id == users["editor"].id))
    c = as_user("editor")
    post_json(c, "/_grid/demo.inbox/action/star", {"ids": [msg.id]})
    db.expire_all()
    assert db.get(Message, msg.id).is_starred
    post_json(c, "/_grid/demo.inbox/action/star", {"ids": [msg.id]})
    db.expire_all()
    assert not db.get(Message, msg.id).is_starred
    post_json(c, "/_grid/demo.inbox/action/archive", {"ids": [msg.id]})
    db.expire_all()
    assert db.get(Message, msg.id).folder == "archive"
    resp = post_json(c, "/_grid/demo.inbox/action/archive", {"ids": [msg.id]}).json()
    assert "none of the selected rows qualify" in resp["message"]
    post_json(c, "/_grid/demo.inbox/action/move_inbox", {"ids": [msg.id]})
    db.expire_all()
    assert db.get(Message, msg.id).folder == "inbox"


def test_home_unread_tile_counts_only_own_messages(as_user, users, items, db):
    db.add(Message(owner_id=users["viewer"].id, sender_name="X", sender_email="x@x.io", subject="s"))
    db.commit()
    html = as_user("viewer").get("/").text
    assert '<span class="stat__value">2</span><span class="stat__label">Unread messages' in html


def test_grid_actions_write_one_audit_event_per_row(as_user, items, db):
    c = as_user("editor")
    post_json(c, "/_grid/demo.work_items/action/approve", {"ids": [items[0].id, items[1].id]})
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "demo.work_items.approve")).all()
    assert len(events) == 2 and len({e.at for e in events}) == 1
