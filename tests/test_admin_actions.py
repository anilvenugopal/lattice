"""Administration grid actions, including the self-protection rules."""

from pathlib import Path

from lattice.kernel.services import users as users_service
from lattice.kernel.sql import sql_queries
from lattice.testing import csrf, login, post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def test_grant_and_revoke_role(as_user, users, db):
    c = as_user("admin")
    vid = users["viewer"].id
    post_json(c, "/_grid/users/action/grant", {"ids": [vid], "values": {"role": "editor"}})
    assert "editor" in users_service.by_id(db, vid)["roles"]
    post_json(c, "/_grid/users/action/revoke", {"ids": [vid], "values": {"role": "editor"}})
    assert "editor" not in users_service.by_id(db, vid)["roles"]


def test_admin_cannot_remove_own_admin_role_or_deactivate_self(as_user, users, db):
    c = as_user("admin")
    aid = users["admin"].id
    post_json(c, "/_grid/users/action/revoke", {"ids": [aid], "values": {"role": "admin"}})
    body = post_json(c, "/_grid/users/action/deactivate", {"ids": [aid]}).json()
    assert "Your own account was skipped" in body["message"]
    c.post(f"/admin/users/{aid}", data={"display_name": "Me", "roles": ["viewer"],
                                        "csrf_token": csrf(c)})
    me = users_service.by_id(db, aid)
    assert me["is_active"] and "admin" in me["roles"]


def test_reset_password_forces_change_and_ends_sessions(as_user, client, users, db):
    login(client, "viewer@test.io")
    c = as_user("admin")
    body = post_json(c, "/_grid/users/action/reset", {"ids": [users["viewer"].id]}).json()
    temp = body["message"].split(": ", 1)[1].split(" ")[0]
    assert users_service.by_id(db, users["viewer"].id)["must_change_password"]
    sessions = db.all(CHECK.sessions_of_user, user_id=users["viewer"].id)
    assert sessions and all(s["revoked_at"] for s in sessions)
    c.cookies.clear()
    assert login(c, "viewer@test.io", temp).status_code == 303


def test_sign_out_everywhere_and_session_revoke(as_user, client, users, db):
    login(client, "editor@test.io")
    c = as_user("admin")
    post_json(c, "/_grid/users/action/signout", {"ids": [users["editor"].id]})
    sessions = db.all(CHECK.sessions_of_user, user_id=users["editor"].id)
    assert sessions and all(s["revoked_at"] for s in sessions)
    login(client, "viewer@test.io")
    c = as_user("admin")
    viewer_session = db.value(CHECK.open_session_of_user, user_id=users["viewer"].id)
    post_json(c, "/_grid/sessions/action/revoke", {"ids": [viewer_session]})
    assert db.one(CHECK.session, id=viewer_session)["revoked_at"] is not None


def test_viewer_cannot_run_admin_actions(as_user, users):
    c = as_user("viewer")
    resp = post_json(c, "/_grid/users/action/grant", {"ids": [users["viewer"].id],
                                                       "values": {"role": "admin"}})
    assert resp.status_code == 403
