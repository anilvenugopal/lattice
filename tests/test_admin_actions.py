"""Administration grid actions, including the self-protection rules."""

from sqlalchemy import select

from lattice.kernel.models import User, UserSession
from lattice.testing import csrf, login, post_json


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


def test_viewer_cannot_run_admin_actions(as_user, users):
    c = as_user("viewer")
    resp = post_json(c, "/_grid/users/action/grant", {"ids": [users["viewer"].id],
                                                       "values": {"role": "admin"}})
    assert resp.status_code == 403
