"""Context for components/timeline.html."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import HTTPException, Request

from lattice.components.timeline.router import can_see
from lattice.components.timeline.spec import TimelineSpec


def build_timeline(request: Request, spec: TimelineSpec, *, linked: bool = True,
                   fixed: dict | None = None) -> dict:
    """Context for one timeline. `linked` and `fixed` work as for build_chart(): a linked
    timeline follows the grid on its page, and a click opens that grid's side panel when
    the spec has no `href`."""
    if not can_see(spec, request.state.user):
        raise HTTPException(403)
    filters = {f"f_{f.key}" for f in spec.source.filters}
    params = [(k, v) for k, v in request.query_params.multi_items()
              if linked and (k in ("q", "view", "shape") or k in filters or k.startswith("x_"))]
    pinned = [(f"x_{key}", str(v)) for key, value in (fixed or {}).items()
              for v in (value if isinstance(value, (list, tuple)) else [value])]
    params += pinned
    return {"spec": spec, "config": {
        "key": spec.key,
        "endpoint": f"/_timeline/{spec.key}/data",
        "grid": spec.source.key if linked else "",
        "params": urlencode(params),
        "fixed": urlencode(pinned),
        "poll": spec.poll_seconds,
    }}
