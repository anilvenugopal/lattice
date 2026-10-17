"""OpenID Connect sign-in: authorization code flow with PKCE.

Works with any provider that publishes `/.well-known/openid-configuration`
(Entra ID, Okta, Keycloak, Auth0, Google). Setup steps: docs/AUTH.md.

The state, nonce and PKCE verifier travel in a signed, 10-minute cookie, so the
flow needs no server-side storage before the user exists.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import settings

FLOW_COOKIE = "oidc_flow"
FLOW_MAX_AGE = 600
_DISCOVERY_TTL = 3600

_discovery: dict = {}
_discovery_at = 0.0
_jwks_client: jwt.PyJWKClient | None = None


class OIDCError(Exception):
    pass


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="oidc-flow")


def discovery() -> dict:
    global _discovery, _discovery_at, _jwks_client
    if not _discovery or time.time() - _discovery_at > _DISCOVERY_TTL:
        url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        _discovery = resp.json()
        _discovery_at = time.time()
        _jwks_client = jwt.PyJWKClient(_discovery["jwks_uri"])
    return _discovery


# Asymmetric algorithms only: "none" and HMAC (keyed with the public client id) are refused.
ALLOWED_ALGORITHMS = ("RS256", "RS384", "RS512", "PS256", "ES256", "ES384")


def _signing_algorithms(meta: dict) -> list[str]:
    advertised = meta.get("id_token_signing_alg_values_supported") or ["RS256"]
    allowed = [a for a in advertised if a in ALLOWED_ALGORITHMS]
    if not allowed:
        raise OIDCError("The provider offers no supported ID token signing algorithm.")
    return allowed


def start(next_url: str) -> tuple[str, str]:
    """Return (authorization URL, signed flow cookie value)."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    flow = {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24),
            "verifier": verifier, "next": next_url}
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": settings.oidc_scopes,
        "state": flow["state"],
        "nonce": flow["nonce"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = discovery()["authorization_endpoint"] + "?" + urlencode(params)
    return url, _serializer().dumps(flow)


def finish(flow_cookie: str | None, state: str, code: str) -> tuple[dict, str]:
    """Exchange the code and validate the ID token. Return (claims, next_url)."""
    try:
        flow = _serializer().loads(flow_cookie or "", max_age=FLOW_MAX_AGE)
    except BadSignature as exc:
        raise OIDCError("Sign-in session expired. Try again.") from exc
    if not secrets.compare_digest(flow["state"], state or ""):
        raise OIDCError("Sign-in state mismatch. Try again.")

    meta = discovery()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oidc_redirect_uri,
        "client_id": settings.oidc_client_id,
        "code_verifier": flow["verifier"],
    }
    if settings.oidc_client_secret:
        data["client_secret"] = settings.oidc_client_secret
    resp = httpx.post(meta["token_endpoint"], data=data, timeout=15)
    if resp.status_code != 200:
        raise OIDCError(f"Token exchange failed ({resp.status_code}).")
    id_token = resp.json().get("id_token")
    if not id_token:
        raise OIDCError("Provider returned no ID token.")

    signing_key = _jwks_client.get_signing_key_from_jwt(id_token)
    try:
        claims = jwt.decode(
            id_token, signing_key.key,
            algorithms=_signing_algorithms(meta),
            audience=settings.oidc_client_id, issuer=meta["issuer"], leeway=60,
        )
    except jwt.PyJWTError as exc:
        raise OIDCError(f"ID token rejected: {exc}") from exc
    if claims.get("nonce") != flow["nonce"]:
        raise OIDCError("ID token nonce mismatch.")
    if not claim_email(claims):
        raise OIDCError("The provider did not return an email address. Add the email scope.")
    return claims, flow.get("next") or "/"


def claim_email(claims: dict) -> str:
    return (claims.get("email") or claims.get("preferred_username") or "").strip().lower()


def logout_url(post_logout_redirect: str) -> str | None:
    """Provider end-session URL, or None when the provider does not publish one."""
    try:
        endpoint = discovery().get("end_session_endpoint")
    except httpx.HTTPError:
        return None
    if not endpoint:
        return None
    return endpoint + "?" + urlencode({"client_id": settings.oidc_client_id,
                                       "post_logout_redirect_uri": post_logout_redirect})
