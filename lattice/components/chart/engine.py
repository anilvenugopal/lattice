"""Aggregates a chart's grid rows in the database and shapes them for the browser.

The grid engine narrows the grid's query by the grid state; this module wraps
that as a subquery and groups it:

    SELECT <x> AS x, <series> AS s, <measure> AS v
    FROM (<the grid's filtered query>) AS c
    GROUP BY 1, 2
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select

from lattice.components.chart.spec import Avg, ChartSpec, Count, Max, Min, Sum, Time
from lattice.components.grid import engine as grid_engine
from lattice.kernel.database import Db

MAX_GROUPS = 5000
OTHER = "__other__"
_AGGREGATES = {Sum: func.sum, Avg: func.avg, Min: func.min, Max: func.max}


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return "" if value is None else value


def _query(chart: ChartSpec, db: Db, user, gq: grid_engine.GridQuery):
    stmt, g = grid_engine.filtered(chart.source, db, user, gq)
    missing = [c for c in chart.columns() if c not in g.c]
    if missing:
        raise ValueError(f"Chart {chart.key!r}: the grid's query has no column "
                         f"{', '.join(map(repr, missing))}")
    c = stmt.subquery("c")
    if isinstance(chart.x, Time):
        x = func.date_trunc(chart.x.unit, c.c[chart.x.column])
    else:
        x = c.c[chart.x]
    measure = (func.count() if isinstance(chart.y, Count)
               else _AGGREGATES[type(chart.y)](c.c[chart.y.column]))
    cols, groups = [x.label("x")], [x]
    if chart.series:
        cols.append(c.c[chart.series].label("s"))
        groups.append(c.c[chart.series])
    query = select(*cols, measure.label("v")).where(x.is_not(None)).group_by(*groups)
    if isinstance(chart.x, Time):
        query = query.order_by(x)
    return query.limit(MAX_GROUPS)


def _top(chart: ChartSpec, points: list[list]) -> tuple[list, list[list]]:
    """Category charts keep the `limit` largest categories; the rest add up to Other."""
    totals: dict = {}
    for x, _s, v in points:
        totals[x] = totals.get(x, 0) + (v or 0)
    ordered = sorted(totals, key=lambda k: totals[k], reverse=True)
    if len(ordered) <= chart.limit:
        return ordered, points
    keep = set(ordered[:chart.limit])
    additive = isinstance(chart.y, (Count, Sum))
    merged: dict = {}
    out = [p for p in points if p[0] in keep]
    if additive:
        for x, s, v in points:
            if x not in keep:
                merged[s] = merged.get(s, 0) + (v or 0)
        out += [[OTHER, s, v] for s, v in merged.items()]
    return ordered[:chart.limit] + ([OTHER] if additive else []), out


def data(chart: ChartSpec, db: Db, user, gq: grid_engine.GridQuery) -> dict:
    """The chart's points and how to draw them, as JSON for static/js/charts.js."""
    rows = grid_engine.read(db, _query(chart, db, user, gq), grid_engine.binds(chart.source, user))
    points = [[_plain(r["x"]), _plain(r.get("s")), _plain(r["v"])] for r in rows]
    time = isinstance(chart.x, Time)
    if time or chart.kind in ("sankey", "choropleth"):
        categories = list(dict.fromkeys(p[0] for p in points))
    else:
        categories, points = _top(chart, points)

    x_col = None if time else chart.source.column(chart.x)
    s_col = chart.source.column(chart.series) if chart.series else None
    x_labels = {str(k): (x_col.labels.get(str(k), str(k)) if x_col else str(k)) for k in categories}
    x_labels[OTHER] = "Other"
    series_keys = list(dict.fromkeys(p[1] for p in points)) if chart.series else [""]
    series = [{"key": str(k),
               "label": (s_col.labels.get(str(k), str(k)) if s_col else str(k)) or "—",
               "tone": s_col.tones.get(str(k), "") if s_col else ""} for k in series_keys]
    if not chart.series:
        series[0]["label"] = chart.measure_label
    return {
        "kind": chart.kind,
        "x": {"type": "time" if time else "category",
              "unit": chart.x.unit if time else ""},
        "categories": [str(k) for k in categories],
        "xLabels": x_labels,
        "xTones": x_col.tones if x_col else {},
        "series": series,
        "points": [[str(x), str(s), v] for x, s, v in points],
        "measure": chart.measure_label,
        "format": chart.format,
        "stacked": chart.stacked,
        "horizontal": chart.horizontal,
        "thresholds": [{"value": t.value, "label": t.label, "tone": t.tone}
                       for t in chart.thresholds],
        "empty": chart.empty_text,
    }
