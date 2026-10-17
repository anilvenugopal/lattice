"""CSRF protection, double-submit cookie.

The middleware sets a random `csrf_token` cookie. Every unsafe request must echo it
in the `X-CSRF-Token` header (HTMX and `app.post()` send it automatically, see
static/js/app.js) or in a `csrf_token` form field (`{{ csrf_field() }}`).
"""

from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request

COOKIE_NAME = "csrf_token"
HEADER_NAME = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def new_token() -> str:
    return secrets.token_urlsafe(32)


async def csrf_protect(request: Request) -> None:
    """Router dependency. Raises 403 when an unsafe request lacks the matching token."""
    if request.method in _SAFE_METHODS:
        return
    expected = request.cookies.get(COOKIE_NAME, "")
    sent = request.headers.get(HEADER_NAME, "")
    if not sent and "form" in request.headers.get("content-type", ""):
        sent = str((await request.form()).get("csrf_token", ""))
    if not expected or not hmac.compare_digest(expected, sent):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token. Reload the page.")
