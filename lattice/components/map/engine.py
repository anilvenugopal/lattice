"""The map's data: points, hexagon and region totals from the grid's query, and areas."""

from __future__ import annotations

import re

from sqlalchemy import func, select

from lattice.components.chart.spec import Count
from lattice.components.grid import engine as grid_engine
from lattice.components.map.spec import Areas, Hexagons, MapSpec, Points, Regions
from lattice.kernel.database import Db
from lattice.kernel.web import fmt

_AGG = {"Sum": func.sum, "Avg": func.avg, "Min": func.min, "Max": func.max}
_FIPS = re.compile(r"^\d+$")


def _measure(measure, c):
    if isinstance(measure, Count):
        return func.count()
    return _AGG[type(measure).__name__](c.c[measure.column])


def _label(measure) -> str:
    return measure.label or f"{type(measure).__name__} of {measure.column}"


def data(spec: MapSpec, db: Db, user, gq: grid_engine.GridQuery) -> dict:
    stmt, g = grid_engine.filtered(spec.source, db, user, gq)
    missing = [c for c in spec.columns() if c not in g.c]
    if missing:
        raise ValueError(f"Map {spec.key!r}: the grid's query has no column "
                         f"{', '.join(map(repr, missing))}")
    c = stmt.subquery("m")
    binds = grid_engine.binds(spec.source, user)
    layers = []
    for i, layer in enumerate(spec.layers):
        out: dict = {"id": f"l{i}", "title": layer.title}
        if isinstance(layer, Points):
            cols = [c.c[layer.lon].label("lon"), c.c[layer.lat].label("lat"), c.c.id.label("id")]
            if layer.color:
                cols.append(c.c[layer.color].label("color"))
            extra = re.findall(r"{(\w+)}", layer.label)
            cols += [c.c[k] for k in extra if k in c.c and k not in ("id", layer.color)]
            rows = grid_engine.read(
                db, select(*cols).where(c.c[layer.lon].is_not(None)).limit(layer.limit + 1), binds)
            col = spec.source.column(layer.color) if layer.color else None
            out |= {"kind": "points", "truncated": len(rows) > layer.limit,
                    "rows": [[float(r["lon"]), float(r["lat"]), str(r.get("color", "") or ""),
                              fmt(layer.label, r)] for r in rows[:layer.limit]],
                    "tones": col.tones if col else {},
                    "labels": col.labels if col else {}}
        elif isinstance(layer, Hexagons | Regions):
            key = c.c[layer.cell if isinstance(layer, Hexagons) else layer.key]
            q = select(key.label("k"), _measure(layer.value, c).label("v")) \
                .where(key.is_not(None)).group_by(key)
            rows = grid_engine.read(db, q, binds)
            out |= {"kind": "hexagons" if isinstance(layer, Hexagons) else "regions",
                    "measure": _label(layer.value),
                    "values": {str(r["k"]): float(r["v"] or 0) for r in rows}}
            if isinstance(layer, Regions):
                width = 2 if layer.map == "us-states" else 5
                out["map"] = layer.map
                out["values"] = {k.zfill(width): v for k, v in out["values"].items()
                                 if _FIPS.match(k)}
        elif isinstance(layer, Areas):
            out |= {"kind": "areas", "tone": layer.tone,
                    "geojson": layer.load(db, user, gq.fixed)}
        layers.append(out)
    return {"layers": layers, "format": spec.format}
