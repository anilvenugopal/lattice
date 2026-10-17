"""One place that decides cookie security flags."""

from __future__ import annotations

from fastapi import Request, Response

from lattice.kernel.config import settings


def is_secure(request: Request) -> bool:
    """COOKIE_SECURE when set; otherwise on in production or when the request is HTTPS.

    Behind a TLS-terminating proxy, run uvicorn with --proxy-headers so the scheme is right.
    """
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    return settings.is_production or request.url.scheme == "https"


def set_cookie(response: Response, request: Request, key: str, value: str, *,
               httponly: bool = True, max_age: int | None = None, path: str = "/") -> None:
    response.set_cookie(key, value, max_age=max_age, path=path, httponly=httponly,
                        samesite="lax", secure=is_secure(request))
