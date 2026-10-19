"""FastAPI dependencies for routes."""

from __future__ import annotations

from fastapi import HTTPException, Request

from lattice.kernel.auth import permissions
from lattice.kernel.auth.sessions import CurrentUser


def current_user(request: Request) -> CurrentUser:
    """Route dependency: the signed-in user (401 when nobody is signed in)."""
    user = request.state.user
    if user is None:
        raise HTTPException(status_code=401)
    return user


def require(permission: str):
    """Route dependency: 403 unless the user has `permission`.

    Usage: `@router.get(..., dependencies=[Depends(require("showcase.items.edit"))])`
    """
    def check(request: Request) -> CurrentUser:
        if permission not in permissions.CATALOGUE:
            raise RuntimeError(f"require({permission!r}): no app declares this permission")
        user = current_user(request)
        if not user.can(permission):
            raise HTTPException(status_code=403, detail="You do not have access to this page.")
        return user
    return check
