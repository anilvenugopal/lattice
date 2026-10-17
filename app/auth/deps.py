"""FastAPI dependencies for routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.auth.sessions import CurrentUser


def current_user(request: Request) -> CurrentUser:
    user = request.state.user
    if user is None:
        raise HTTPException(status_code=401)
    return user


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
