"""Builds the template context for a chart: render it with `chart(c)` from components/chart.html."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import HTTPException, Request

from lattice.components.chart.router import can_see
from lattice.components.chart.spec import ChartSpec


def build_chart(request: Request, chart: ChartSpec, *, linked: bool = True,
                fixed: dict | None = None) -> dict:
    """Context for one chart on a page.

    linked=True: the chart follows the grid with the same source on this page. It starts
    from the page URL's grid state (a grid that owns the URL) and reloads whenever that
    grid's search, filters or view change. linked=False: it shows the grid's defaults.
    fixed: column -> value (or list) the rows are narrowed to, as for an embedded grid.
    """
    if not can_see(chart, request.state.user):
        raise HTTPException(403)
    filters = {f"f_{f.key}" for f in chart.source.filters}
    params = [(k, v) for k, v in request.query_params.multi_items()
              if linked and (k in ("q", "view", "shape") or k in filters or k.startswith("x_"))]
    # The page's fixed values; narrowings from the URL travel with the grid's state.
    pinned = [(f"x_{key}", str(v)) for key, value in (fixed or {}).items()
              for v in (value if isinstance(value, (list, tuple)) else [value])]
    params += pinned
    return {
        "spec": chart,
        "config": {
            "key": chart.key,
            "endpoint": f"/_chart/{chart.key}/data",
            "grid": chart.source.key if linked else "",
            "params": urlencode(params),
            "fixed": urlencode(pinned),
            "drill": chart.drill,
        },
    }
