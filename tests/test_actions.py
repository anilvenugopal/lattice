"""Every grid action of the example features and Administration, including role and self guards."""

from sqlalchemy import select

from app.models import AuditEvent, Job, Message, User, UserSession
from tests.conftest import csrf, login, post_json


def _jobs(db, *statuses):
    rows = [Job(name=f"job {s}", job_type="sync", status=s) for s in statuses]
    db.add_all(rows)
    db.commit()
    return rows


# ── Jobs ──────────────────────────────────────────────────────────────────────

def test_run_job_creates_a_queued_job(as_user, db):
    c = as_user("viewer")
    resp = post_json(c, "/_grid/jobs/action/new", {"values": {"name": "Nightly", "job_type": "export"}})
    assert resp.status_code == 200
    job = db.scalar(select(Job).where(Job.name == "Nightly"))
    assert job.status == "queued" and job.job_type == "export"


def test_retry_only_failed_or_cancelled_and_cancel_only_active(as_user, db):
    failed, done, running = _jobs(db, "failed", "succeeded", "running")
    c = as_user("editor")
    body = post_json(c, "/_grid/jobs/action/retry", {"ids": [failed.id, done.id]}).json()
    assert "1 skipped" in body["message"]
    body = post_json(c, "/_grid/jobs/action/cancel", {"ids": [running.id, done.id]}).json()
    assert "1 skipped" in body["message"]
    db.expire_all()
    assert (db.get(Job, failed.id).status, db.get(Job, failed.id).attempts) == ("queued", 2)
    assert db.get(Job, done.id).status == "succeeded"
    assert db.get(Job, running.id).status == "cancelled"


# ── Inbox ─────────────────────────────────────────────────────────────────────

def test_inbox_star_archive_and_move_back(as_user, users, items, db):
    msg = db.scalar(select(Message).where(Message.owner_id == users["editor"].id))
    c = as_user("editor")
    post_json(c, "/_grid/inbox/action/star", {"ids": [msg.id]})
    db.expire_all()
    assert db.get(Message, msg.id).is_starred
    post_json(c, "/_grid/inbox/action/star", {"ids": [msg.id]})
    db.expire_all()
    assert not db.get(Message, msg.id).is_starred
    post_json(c, "/_grid/inbox/action/archive", {"ids": [msg.id]})
    db.expire_all()
    assert db.get(Message, msg.id).folder == "archive"
    resp = post_json(c, "/_grid/inbox/action/archive", {"ids": [msg.id]}).json()
    assert "none of the selected rows qualify" in resp["message"]
    post_json(c, "/_grid/inbox/action/move_inbox", {"ids": [msg.id]})
    db.expire_all()
    assert db.get(Message, msg.id).folder == "inbox"


def test_home_unread_tile_counts_only_own_messages(as_user, users, items, db):
    db.add(Message(owner_id=users["viewer"].id, sender_name="X", sender_email="x@x.io", subject="s"))
    db.commit()
    html = as_user("viewer").get("/").text
    assert '<span class="stat__value">2</span><span class="stat__label">Unread messages' in html


# ── Administration: users ─────────────────────────────────────────────────────

def test_grant_and_revoke_role(as_user, users, db):
    c = as_user("admin")
    vid = users["viewer"].id
    post_json(c, "/_grid/users/action/grant", {"ids": [vid], "values": {"role": "editor"}})
    db.expire_all()
    assert "editor" in db.get(User, vid).role_codes
    post_json(c, "/_grid/users/action/revoke", {"ids": [vid], "values": {"role": "editor"}})
    db.expire_all()
    assert "editor" not in db.get(User, vid).role_codes


def test_admin_cannot_remove_own_admin_role_or_deactivate_self(as_user, users, db):
    c = as_user("admin")
    aid = users["admin"].id
    post_json(c, "/_grid/users/action/revoke", {"ids": [aid], "values": {"role": "admin"}})
    body = post_json(c, "/_grid/users/action/deactivate", {"ids": [aid]}).json()
    assert "Your own account was skipped" in body["message"]
    c.post(f"/admin/users/{aid}", data={"display_name": "Me", "roles": ["viewer"],
                                        "csrf_token": csrf(c)})
    db.expire_all()
    me = db.get(User, aid)
    assert me.is_active and "admin" in me.role_codes


def test_reset_password_forces_change_and_ends_sessions(as_user, client, users, db):
    login(client, "viewer@test.io")
    c = as_user("admin")
    body = post_json(c, "/_grid/users/action/reset", {"ids": [users["viewer"].id]}).json()
    temp = body["message"].split(": ", 1)[1].split(" ")[0]
    db.expire_all()
    assert db.get(User, users["viewer"].id).must_change_password
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == users["viewer"].id)).all()
    assert all(s.revoked_at for s in sessions)
    c.cookies.clear()
    assert login(c, "viewer@test.io", temp).status_code == 303


def test_sign_out_everywhere_and_session_revoke(as_user, client, users, db):
    login(client, "editor@test.io")
    c = as_user("admin")
    post_json(c, "/_grid/users/action/signout", {"ids": [users["editor"].id]})
    db.expire_all()
    assert all(s.revoked_at for s in db.scalars(
        select(UserSession).where(UserSession.user_id == users["editor"].id)))
    login(client, "viewer@test.io")
    c = as_user("admin")
    viewer_session = db.scalar(select(UserSession.id).where(
        UserSession.user_id == users["viewer"].id, UserSession.revoked_at.is_(None)))
    post_json(c, "/_grid/sessions/action/revoke", {"ids": [viewer_session]})
    db.expire_all()
    assert db.get(UserSession, viewer_session).revoked_at is not None


def test_viewer_cannot_run_admin_or_editor_actions(as_user, items):
    c = as_user("viewer")
    assert post_json(c, "/_grid/users/action/grant", {"ids": [1], "values": {"role": "admin"}}).status_code == 403
    assert post_json(c, "/_grid/work_items/action/approve", {"ids": [items[0].id]}).status_code == 403


def test_grid_actions_write_one_audit_event_per_row(as_user, items, db):
    c = as_user("editor")
    post_json(c, "/_grid/work_items/action/approve", {"ids": [items[0].id, items[1].id]})
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "work_items.approve")).all()
    assert len(events) == 2 and len({e.at for e in events}) == 1
