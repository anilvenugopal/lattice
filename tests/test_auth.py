from sqlalchemy import select

from app.auth.sessions import COOKIE_NAME as SESSION_COOKIE
from app.models import AuditEvent, UserSession
from tests.conftest import PASSWORD, csrf, login, make_user


def test_anonymous_request_redirects_to_login_with_next(client, users):
    resp = client.get("/work?view=mine", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/auth/login?next=/work%3Fview%3Dmine"


def test_htmx_request_gets_hx_redirect(client, users):
    resp = client.get("/work", headers={"HX-Request": "true"}, follow_redirects=False)
    assert resp.status_code == 200
    assert resp.headers["HX-Redirect"].startswith("/auth/login")


def test_password_login_and_logout(client, users, db):
    assert login(client, "admin@test.io", "wrong").status_code == 401
    resp = login(client, "ADMIN@test.io")
    assert resp.status_code == 303
    assert client.get("/").status_code == 200

    token = client.cookies[SESSION_COOKIE]
    stored = db.scalars(select(UserSession.id)).all()
    assert token not in stored and len(stored) == 1     # only the hash is stored

    client.post("/auth/logout", data={"csrf_token": csrf(client)})
    assert client.get("/", follow_redirects=False).status_code == 302
    actions = db.scalars(select(AuditEvent.action)).all()
    assert "auth.login_failed" in actions and "auth.login" in actions


def test_login_rejects_open_redirect(client, users):
    token = csrf(client)
    resp = client.post("/auth/login", data={"email": "admin@test.io", "password": PASSWORD,
                                            "csrf_token": token, "next": "//evil.example"},
                       follow_redirects=False)
    assert resp.headers["location"] == "/"


def test_post_without_csrf_token_is_rejected(client, users):
    csrf(client)
    resp = client.post("/auth/login", data={"email": "admin@test.io", "password": PASSWORD})
    assert resp.status_code == 403


def test_inactive_and_sso_only_users_cannot_use_password(client, db):
    make_user(db, "gone@test.io", is_active=False)
    make_user(db, "sso@test.io", password=None)
    assert login(client, "gone@test.io").status_code == 401
    assert login(client, "sso@test.io", "").status_code == 401


def test_must_change_password_gate(client, db):
    make_user(db, "new@test.io", must_change_password=True)
    login(client, "new@test.io")
    assert client.get("/work", follow_redirects=False).headers["location"] == "/auth/change-password"
    resp = client.post("/auth/change-password", data={
        "current": PASSWORD, "new": "short", "confirm": "short", "csrf_token": csrf(client)})
    assert resp.status_code == 400
    resp = client.post("/auth/change-password", data={
        "current": PASSWORD, "new": "BrandNewPass99", "confirm": "BrandNewPass99",
        "csrf_token": csrf(client)}, follow_redirects=False)
    assert resp.status_code == 303
    assert client.get("/work").status_code == 200


def test_user_without_role_sees_pending_page(client, db):
    make_user(db, "norole@test.io", roles=())
    login(client, "norole@test.io")
    assert client.get("/", follow_redirects=False).headers["location"] == "/auth/pending"
    assert "Access pending" in client.get("/auth/pending").text


def test_viewer_cannot_open_administration(as_user):
    c = as_user("viewer")
    assert c.get("/admin/users").status_code == 403
    assert c.get("/_grid/users/rows").status_code == 403
    assert 'href="/admin/users"' not in c.get("/").text


def test_revoking_sessions_on_deactivate(as_user, users, client):
    c = as_user("admin")
    from tests.conftest import post_json
    resp = post_json(c, "/_grid/users/action/deactivate", {"ids": [users["editor"].id]})
    assert resp.status_code == 200 and "Deactivated 1" in resp.json()["message"]
    c.cookies.clear()
    assert login(c, "editor@test.io").status_code == 401


def test_session_helpers_leave_the_commit_to_the_caller(db, users):
    from app.auth.sessions import revoke_user_sessions
    from app.models import UserSession, utcnow
    db.add(UserSession(id="s1", user_id=users["editor"].id, expires_at=utcnow()))
    db.commit()
    revoke_user_sessions(db, users["editor"].id)
    db.rollback()
    assert db.get(UserSession, "s1").revoked_at is None


def test_logout_and_own_session_revocation_are_audited(as_user, users, db):
    c = as_user("viewer")
    c.post("/account/sessions/revoke-others", headers={"X-CSRF-Token": csrf(c)})
    c.post("/auth/logout", data={"csrf_token": csrf(c)})
    actions = db.scalars(select(AuditEvent.action).where(
        AuditEvent.target_id == str(users["viewer"].id))).all()
    assert "user.session_revoked" in actions and "auth.logout" in actions


def test_unknown_email_still_runs_bcrypt(client, users, monkeypatch):
    import bcrypt
    calls = []
    real = bcrypt.checkpw
    monkeypatch.setattr(bcrypt, "checkpw", lambda *a: calls.append(1) or real(*a))
    assert login(client, "nobody@test.io").status_code == 401
    assert calls


def test_cookies_are_secure_in_production(client, users, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    resp = login(client, "admin@test.io")
    assert "secure" in resp.headers["set-cookie"].lower()


def test_oidc_refuses_symmetric_algorithms():
    import pytest as _pytest

    from app.auth import oidc
    assert oidc._signing_algorithms({"id_token_signing_alg_values_supported": ["HS256", "RS256"]}) == ["RS256"]
    with _pytest.raises(oidc.OIDCError):
        oidc._signing_algorithms({"id_token_signing_alg_values_supported": ["HS256", "none"]})
