"""OIDC flow against a fake provider: discovery, token endpoint and JWKS are stubbed."""

import json
import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from lattice.kernel.auth import oidc
from lattice.kernel.config import settings
from lattice.kernel.models import User
from tests.conftest import csrf, make_user

ISSUER = "https://idp.test"
CLIENT_ID = "lattice"


@pytest.fixture
def idp(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="k1", alg="RS256", use="sig")
    state = {"claims": {}}

    monkeypatch.setattr(settings, "oidc_issuer", ISSUER)
    monkeypatch.setattr(settings, "oidc_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "oidc_default_role", "viewer")
    monkeypatch.setattr(oidc, "_discovery", {
        "issuer": ISSUER, "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token", "jwks_uri": f"{ISSUER}/jwks",
        "end_session_endpoint": f"{ISSUER}/logout",
        "id_token_signing_alg_values_supported": ["RS256"]})
    monkeypatch.setattr(oidc, "_discovery_at", time.time())

    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            return jwt.PyJWK(jwk)
    monkeypatch.setattr(oidc, "_jwks_client", FakeJwks())

    class Resp:
        status_code = 200

        def __init__(self, body):
            self._body = body

        def json(self):
            return self._body

    def fake_post(url, data, timeout):
        claims = {"iss": ISSUER, "aud": CLIENT_ID, "exp": int(time.time()) + 300,
                  "iat": int(time.time()), **state["claims"]}
        return Resp({"id_token": jwt.encode(claims, key, "RS256", headers={"kid": "k1"})})
    monkeypatch.setattr(oidc.httpx, "post", fake_post)
    yield state


def sign_in(client, idp, claims, nonce_override=None):
    resp = client.get("/auth/oidc/start?next=/demo/jobs", follow_redirects=False)
    params = parse_qs(urlparse(resp.headers["location"]).query)
    assert params["code_challenge_method"] == ["S256"]
    idp["claims"] = {"nonce": nonce_override or params["nonce"][0], **claims}
    return client.get(f"/auth/oidc/callback?code=abc&state={params['state'][0]}",
                      follow_redirects=False)


def test_first_sso_sign_in_creates_user_with_default_role(client, db, idp):
    resp = sign_in(client, idp, {"sub": "u-1", "email": "New.Person@corp.io", "name": "New Person"})
    assert resp.status_code == 303 and resp.headers["location"] == "/demo/jobs"
    user = db.scalar(select(User).where(User.email == "new.person@corp.io"))
    assert user.oidc_subject == "u-1" and user.role_codes == ["viewer"] and user.password_hash is None
    assert client.get("/demo/jobs").status_code == 200


def test_sso_links_existing_account_by_verified_email(client, db, idp, users):
    resp = sign_in(client, idp, {"sub": "u-2", "email": "editor@test.io", "email_verified": True})
    assert resp.status_code == 303
    db.expire_all()
    assert db.get(User, users["editor"].id).oidc_subject == "u-2"


def test_unverified_email_does_not_link_existing_account(client, db, idp, users):
    resp = sign_in(client, idp, {"sub": "u-5", "email": "admin@test.io"})
    assert resp.status_code == 403 and "Ask an administrator" in resp.text
    db.expire_all()
    assert db.get(User, users["admin"].id).oidc_subject is None
    assert client.get("/", follow_redirects=False).status_code == 302


def test_trusted_email_setting_links_without_email_verified(client, db, idp, users, monkeypatch):
    monkeypatch.setattr(settings, "oidc_trust_email", True)
    assert sign_in(client, idp, {"sub": "u-6", "email": "viewer@test.io"}).status_code == 303
    db.expire_all()
    assert db.get(User, users["viewer"].id).oidc_subject == "u-6"


def test_preferred_username_never_links(client, db, idp, users, monkeypatch):
    monkeypatch.setattr(settings, "oidc_trust_email", True)
    resp = sign_in(client, idp, {"sub": "u-7", "preferred_username": "admin@test.io"})
    assert resp.status_code == 403
    db.expire_all()
    assert db.get(User, users["admin"].id).oidc_subject is None


def test_nonce_mismatch_is_rejected(client, db, idp):
    resp = sign_in(client, idp, {"sub": "u-3", "email": "x@corp.io"}, nonce_override="forged")
    assert resp.status_code == 400 and "nonce" in resp.text


def test_state_mismatch_is_rejected(client, db, idp):
    client.get("/auth/oidc/start", follow_redirects=False)
    resp = client.get("/auth/oidc/callback?code=abc&state=wrong")
    assert resp.status_code == 400


def test_deactivated_user_cannot_sign_in_with_sso(client, db, idp):
    make_user(db, "off@corp.io", is_active=False, oidc_subject="u-4")
    assert sign_in(client, idp, {"sub": "u-4", "email": "off@corp.io"}).status_code == 403


def test_login_page_shows_sso_button(client, idp):
    assert "Continue with" in client.get("/auth/login").text


def test_sso_logout_redirects_to_provider_end_session(client, db, idp):
    sign_in(client, idp, {"sub": "u-9", "email": "x9@corp.io"})
    token = csrf(client)
    resp = client.post("/auth/logout", data={"csrf_token": token}, follow_redirects=False)
    assert resp.headers["location"].startswith(f"{ISSUER}/logout?")
    assert client.get("/", follow_redirects=False).status_code == 302
