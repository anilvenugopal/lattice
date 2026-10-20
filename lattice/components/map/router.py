"""Map endpoint, shared by every registered MapSpec.

  GET /_map/{key}/data?<grid state>   the map's layers (JSON)
  GET /_map/{key}/places?q=…          places for the search box (MapSpec.search)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from lattice.components.grid import engine as grid_engine
from lattice.components.map import engine
from lattice.components.map.spec import MapSpec
from lattice.kernel.auth.deps import current_user
from lattice.kernel.database import Db, get_db

REGISTRY: dict[str, MapSpec] = {}

router = APIRouter(prefix="/_map")


def register(spec: MapSpec) -> MapSpec:
    if spec.key in REGISTRY and REGISTRY[spec.key] is not spec:
        raise ValueError(f"Map key {spec.key!r} is already registered")
    spec.check()
    REGISTRY[spec.key] = spec
    return spec


def can_see(spec: MapSpec, user) -> bool:
    return user.can(spec.permission) and user.can(spec.source.permission)


@router.get("/{key}/places")
def map_places(key: str, q: str = "", db: Db = Depends(get_db), user=Depends(current_user)):
    spec = REGISTRY.get(key)
    if spec is None or spec.search is None:
        raise HTTPException(404)
    if not can_see(spec, user):
        raise HTTPException(403)
    return {"places": [{"label": p["label"], "lon": float(p["lon"]), "lat": float(p["lat"])}
                       for p in spec.search(db, user, q.strip()[:100])[:10]]}


@router.get("/{key}/data")
def map_data(key: str, request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    spec = REGISTRY.get(key)
    if spec is None:
        raise HTTPException(404)
    if not can_see(spec, user):
        raise HTTPException(403)
    gq = grid_engine.GridQuery.from_params(request.query_params, spec.source)
    try:
        return engine.data(spec, db, user, gq)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from None
