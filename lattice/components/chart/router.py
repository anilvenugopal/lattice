"""Chart endpoint, shared by every registered ChartSpec.

  GET /_chart/{key}/data?<grid state>   the chart's aggregated points (JSON)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from lattice.components.chart import engine
from lattice.components.chart.spec import ChartSpec
from lattice.components.grid import engine as grid_engine
from lattice.kernel.auth.deps import current_user
from lattice.kernel.database import Db, get_db

REGISTRY: dict[str, ChartSpec] = {}

router = APIRouter(prefix="/_chart")


def register(chart: ChartSpec) -> ChartSpec:
    if chart.key in REGISTRY and REGISTRY[chart.key] is not chart:
        raise ValueError(f"Chart key {chart.key!r} is already registered")
    chart.check()
    REGISTRY[chart.key] = chart
    return chart


def can_see(chart: ChartSpec, user) -> bool:
    return user.can(chart.permission) and user.can(chart.source.permission)


@router.get("/{key}/data")
def chart_data(key: str, request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    chart = REGISTRY.get(key)
    if chart is None:
        raise HTTPException(404)
    if not can_see(chart, user):
        raise HTTPException(403)
    gq = grid_engine.GridQuery.from_params(request.query_params, chart.source)
    try:
        return engine.data(chart, db, user, gq)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from None
