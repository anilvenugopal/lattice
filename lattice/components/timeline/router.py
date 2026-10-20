"""Timeline endpoint, shared by every registered TimelineSpec.

  GET /_timeline/{key}/data?<grid state>&from=…&to=…   lanes and bars in the window (JSON)
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from lattice.components.grid import engine as grid_engine
from lattice.components.timeline import engine
from lattice.components.timeline.spec import TimelineSpec
from lattice.kernel.auth.deps import current_user
from lattice.kernel.database import Db, get_db

REGISTRY: dict[str, TimelineSpec] = {}

router = APIRouter(prefix="/_timeline")


def register(spec: TimelineSpec) -> TimelineSpec:
    if spec.key in REGISTRY and REGISTRY[spec.key] is not spec:
        raise ValueError(f"Timeline key {spec.key!r} is already registered")
    spec.check()
    REGISTRY[spec.key] = spec
    return spec


def can_see(spec: TimelineSpec, user) -> bool:
    return user.can(spec.permission) and user.can(spec.source.permission)


def _when(value: str | None) -> datetime | None:
    """An ISO time from the browser ("…Z"), as naive UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, detail=f"Not a time: {value!r}") from None
    return parsed.astimezone(UTC).replace(tzinfo=None) if parsed.tzinfo else parsed


@router.get("/{key}/data")
def timeline_data(key: str, request: Request, db: Db = Depends(get_db),
                  user=Depends(current_user)):
    spec = REGISTRY.get(key)
    if spec is None:
        raise HTTPException(404)
    if not can_see(spec, user):
        raise HTTPException(403)
    gq = grid_engine.GridQuery.from_params(request.query_params, spec.source)
    start, end = _when(request.query_params.get("from")), _when(request.query_params.get("to"))
    if (start is None) != (end is None) or (start and start >= end):
        raise HTTPException(400, detail="Give both from and to, with from before to")
    try:
        return engine.data(spec, db, user, gq, start, end)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from None
