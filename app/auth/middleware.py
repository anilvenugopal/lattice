"""Authentication middleware.

Order of gates for every non-public path:
  1. valid session            → else redirect to /auth/login
  2. must_change_password     → else redirect to /auth/change-password
  3. at least one role        → else redirect to /auth/pending
Sets `request.state.user` (CurrentUser) and `request.state.csrf_token`.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app import db as app_db
from app.auth import csrf
from app.auth.cookies import set_cookie
from app.auth.sessions import COOKIE_NAME, load_session

PUBLIC_PREFIXES = ("/static/", "/auth/login", "/auth/oidc/", "/health")
CHANGE_PASSWORD_EXEMPT = ("/auth/change-password", "/auth/logout")
NO_ROLE_EXEMPT = ("/auth/pending", "/auth/logout", "/auth/change-password")


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def redirect(request: Request, url: str) -> Response:
    """HTMX requests need HX-Redirect; a 302 would be swapped into the page."""
    if is_htmx(request):
        return Response(status_code=200, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=302)


def _load(session_id: str):
    with app_db.SessionLocal() as db:
        return load_session(db, session_id)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get(csrf.COOKIE_NAME) or csrf.new_token()
        request.state.csrf_token = token
        request.state.user = None
        response = await self._gate(request, call_next)
        if csrf.COOKIE_NAME not in request.cookies:
            set_cookie(response, request, csrf.COOKIE_NAME, token, httponly=False)
        return response

    async def _gate(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        session_id = request.cookies.get(COOKIE_NAME)
        user = await run_in_threadpool(_load, session_id) if session_id else None
        if user is None:
            target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            nxt = "" if path == "/" else f"?next={quote(target)}"
            return redirect(request, f"/auth/login{nxt}")
        if user.must_change_password and not path.startswith(CHANGE_PASSWORD_EXEMPT):
            return redirect(request, "/auth/change-password")
        if not user.roles and not path.startswith(NO_ROLE_EXEMPT):
            return redirect(request, "/auth/pending")

        request.state.user = user
        return await call_next(request)
