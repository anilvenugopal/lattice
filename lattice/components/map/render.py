"""Builds the template context for a map: render it with `map_view(m)` from components/map.html."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import HTTPException, Request

from lattice.components.map.router import can_see
from lattice.components.map.spec import MapSpec

BASEMAP = Path(__file__).parents[2] / "static" / "maps" / "basemap"


def basemap_url() -> str:
    """The self-hosted basemap, when `make maps` has fetched it; "" for outlines only."""
    return "/static/maps/basemap/us.pmtiles" if (BASEMAP / "us.pmtiles").is_file() else ""


def build_map(request: Request, spec: MapSpec, *, linked: bool = True,
              fixed: dict | None = None) -> dict:
    """Context for one map. `linked` and `fixed` work as for build_chart()."""
    if not can_see(spec, request.state.user):
        raise HTTPException(403)
    filters = {f"f_{f.key}" for f in spec.source.filters}
    params = [(k, v) for k, v in request.query_params.multi_items()
              if linked and (k in ("q", "view") or k in filters)]
    for key, value in (fixed or {}).items():
        params += [(f"x_{key}", str(v)) for v in (value if isinstance(value, (list, tuple))
                                                  else [value])]
    return {"spec": spec, "config": {
        "key": spec.key,
        "endpoint": f"/_map/{spec.key}/data",
        "grid": spec.source.key if linked else "",
        "params": urlencode(params),
        "fixed": urlencode([(k, v) for k, v in params if k.startswith("x_")]),
        "basemap": basemap_url(),
    }}
