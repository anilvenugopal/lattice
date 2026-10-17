"""Sign-in (password and OIDC), sign-out, forced password change, pending access."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from lattice.kernel.auth import oidc
from lattice.kernel.auth.cookies import set_cookie
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user
from lattice.kernel.auth.passwords import hash_password, policy_errors, verify_password
from lattice.kernel.auth.sessions import (
    COOKIE_NAME,
    create_session,
    revoke_session,
    revoke_user_sessions,
    session_key,
)
from lattice.kernel.config import settings
from lattice.kernel.db import get_db
from lattice.kernel.dev_seed import DEV_USERS
from lattice.kernel.models import User, UserSession
from lattice.kernel.services import audit, preferences, users
from lattice.kernel.web import render

router = APIRouter(prefix="/auth", dependencies=[Depends(csrf_protect)])


def safe_next(url: str | None) -> str:
    """Only same-site paths; blocks open redirects like //evil.example."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return "/"


def _landing(user: User, db: Session, nxt: str) -> str:
    if nxt != "/":
        return nxt
    return safe_next(preferences.load(db, user.id).get("landing_page", "/"))


def _signed_in(request: Request, db: Session, user: User, method: str, nxt: str):
    token = create_session(db, user, request.client.host if request.client else "",
                           request.headers.get("user-agent", ""), method)
    db.commit()
    response = RedirectResponse(_landing(user, db, nxt), status_code=303)
    set_cookie(response, request, COOKIE_NAME, token, max_age=settings.session_max_hours * 3600)
    return response


def _login_page(request: Request, nxt: str = "/", error: str = "", email: str = "",
                status_code: int = 200):
    return render(request, "auth/login.html", status_code=status_code,
                  next=nxt, error=error, email=email,
                  password_enabled=settings.password_login_enabled,
                  oidc_enabled=settings.oidc_enabled, oidc_label=settings.oidc_provider_label,
                  dev_users=DEV_USERS if settings.app_env == "development" else [])


@router.get("/login")
def login_page(request: Request, next: str = "/", error: str = ""):
    return _login_page(request, safe_next(next), error)


@router.post("/login")
def login(request: Request, email: str = Form(""), password: str = Form(""),
          next: str = Form("/"), db: Session = Depends(get_db)):
    if not settings.password_login_enabled:
        return _login_page(request, error="Password sign-in is disabled.", status_code=403)
    email = users.normalize_email(email)
    user = users.by_email(db, email)
    # Always run bcrypt, so the response time does not reveal whether the email exists.
    password_ok = verify_password(password, user.password_hash if user else None)
    if user is None or not user.is_active or not password_ok:
        audit.record(db, user.id if user else None, "auth.login_failed",
                     f"Failed password sign-in for {email}", "users", user.id if user else "")
        db.commit()
        return _login_page(request, safe_next(next), "Email or password is incorrect.", email, 401)
    audit.record(db, user.id, "auth.login", f"{user.email} signed in with password",
                 "users", user.id)
    return _signed_in(request, db, user, "password", safe_next(next))


@router.get("/oidc/start")
def oidc_start(request: Request, next: str = "/"):
    if not settings.oidc_enabled:
        return RedirectResponse("/auth/login", status_code=303)
    try:
        url, flow = oidc.start(safe_next(next))
    except httpx.HTTPError:
        return RedirectResponse("/auth/login?error=Identity+provider+is+unreachable",
                                status_code=303)
    response = RedirectResponse(url, status_code=303)
    set_cookie(response, request, oidc.FLOW_COOKIE, flow, max_age=oidc.FLOW_MAX_AGE,
               path="/auth/oidc/")
    return response


def _email_is_trusted(claims: dict) -> bool:
    return settings.oidc_trust_email or claims.get("email_verified") in (True, "true")


def provision_oidc_user(db: Session, claims: dict) -> User:
    """Find the user by subject, then by verified email (linking the account), else create one.

    Linking uses only the `email` claim, and only when it is verified or OIDC_TRUST_EMAIL
    is set. Raises OIDCError when the identity matches an existing account that may not
    be linked, so an unverified email cannot take over that account.
    """
    sub = claims["sub"]
    email = oidc.claim_email(claims)
    user = db.scalar(select(User).where(User.oidc_subject == sub))
    if user is None:
        existing = users.by_email(db, email)
        if existing is not None:
            claimed = users.normalize_email(claims.get("email"))
            if claimed != email or not _email_is_trusted(claims):
                raise oidc.OIDCError("An account with this email already exists. "
                                     "Ask an administrator to link your account.")
            user = existing
            user.oidc_subject = sub
            audit.record(db, user.id, "user.oidc_linked", f"Linked SSO identity to {email}",
                         "users", user.id)
    if user is None:
        role = settings.oidc_default_role
        user = users.create(db, email, claims.get("name") or email.split("@")[0],
                            roles=[role] if role else [], oidc_subject=sub)
        audit.record(db, user.id, "user.created", f"{email} created on first SSO sign-in",
                     "users", user.id, {"default_role": role or None})
    db.commit()
    return user


@router.get("/oidc/callback")
def oidc_callback(request: Request, code: str = "", state: str = "", error: str = "",
                  error_description: str = "", db: Session = Depends(get_db)):
    if error:
        return _login_page(request, error=error_description or error, status_code=400)
    try:
        claims, nxt = oidc.finish(request.cookies.get(oidc.FLOW_COOKIE), state, code)
    except (oidc.OIDCError, httpx.HTTPError) as exc:
        return _login_page(request, error=str(exc), status_code=400)
    try:
        user = provision_oidc_user(db, claims)
    except oidc.OIDCError as exc:
        return _login_page(request, error=str(exc), status_code=403)
    if not user.is_active:
        return _login_page(request, error="Your account is deactivated.", status_code=403)
    audit.record(db, user.id, "auth.login", f"{user.email} signed in with SSO", "users", user.id)
    response = _signed_in(request, db, user, "oidc", safe_next(nxt))
    response.delete_cookie(oidc.FLOW_COOKIE, path="/auth/oidc/")
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    target = "/auth/login"
    if token:
        session_id = session_key(token)
        sess = db.get(UserSession, session_id)
        if sess and sess.auth_method == "oidc" and settings.oidc_enabled:
            base = str(request.base_url).rstrip("/")
            target = oidc.logout_url(base + "/auth/login") or target
        revoke_session(db, session_id)
        if sess:
            audit.record(db, sess.user_id, "auth.logout", "Signed out", "users", sess.user_id)
        db.commit()
    response = RedirectResponse(target, status_code=303)
    response.delete_cookie(COOKIE_NAME)
    if request.headers.get("HX-Request"):
        response.headers["HX-Redirect"] = target
    return response


@router.get("/change-password")
def change_password_page(request: Request, user=Depends(current_user)):
    return render(request, "auth/change_password.html", errors=[],
                  forced=user.must_change_password)


@router.post("/change-password")
def change_password(request: Request, current: str = Form(""), new: str = Form(""),
                    confirm: str = Form(""), db: Session = Depends(get_db),
                    user=Depends(current_user)):
    row = db.get(User, user.id)
    errors = []
    if row.password_hash and not verify_password(current, row.password_hash):
        errors.append("Current password is incorrect")
    if new != confirm:
        errors.append("New passwords do not match")
    errors += policy_errors(new)
    if errors:
        return render(request, "auth/change_password.html", status_code=400, errors=errors,
                      forced=user.must_change_password)
    row.password_hash = hash_password(new)
    row.must_change_password = False
    audit.record(db, user.id, "user.password_changed", f"{row.email} changed their password",
                 "users", user.id)
    revoke_user_sessions(db, user.id, keep=user.session_id)
    db.commit()
    return RedirectResponse("/", status_code=303)


@router.get("/pending")
def pending(request: Request, user=Depends(current_user)):
    if user.roles:
        return RedirectResponse("/", status_code=303)
    return render(request, "auth/pending.html")
