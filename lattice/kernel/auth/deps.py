"""FastAPI dependencies for routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from lattice.kernel.auth.sessions import CurrentUser


def current_user(request: Request) -> CurrentUser:
    """Route dependency: the signed-in user (401 when nobody is signed in)."""
    user = request.state.user
    if user is None:
        raise HTTPException(status_code=401)
    return user


def require(permission: str):
    """Route dependency: 403 unless the user has `permission`.

    Usage: `@router.get(..., dependencies=[Depends(require("demo.work.edit"))])`
    """
    def check(request: Request) -> CurrentUser:
        user = current_user(request)
        if not user.can(permission):
            raise HTTPException(status_code=403, detail="You do not have access to this page.")
        return user
    return check


def require_roles(*roles: str):
    """Route dependency: 403 unless the user holds one of `roles`.

    Usage: `@router.get(..., dependencies=[Depends(require_roles("admin"))])`
    """
    def check(request: Request) -> CurrentUser:
        user = current_user(request)
        if not user.has_any(roles):
            raise HTTPException(status_code=403, detail="You do not have access to this page.")
        return user
    return check
