"""The timeline's data: the window, its lanes and bars, from the grid's query (ADR 0014)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select

from lattice.components.grid import engine as grid_engine
from lattice.components.timeline.spec import TimelineSpec
from lattice.kernel.database import Db
from lattice.kernel.web import fmt, fmt_url, label_for


def _utc(value: datetime | None) -> datetime | None:
    """Naive values are UTC already (Lattice's rule); aware ones are converted."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def iso(value: datetime | None) -> str | None:
    return _utc(value).isoformat() + "Z" if value is not None else None


def data(spec: TimelineSpec, db: Db, user, gq: grid_engine.GridQuery,
         start: datetime | None = None, end: datetime | None = None) -> dict:
    """Bars overlapping the window [start, end] (naive UTC); without one, every bar."""
    stmt, g = grid_engine.filtered(spec.source, db, user, gq)
    missing = [c for c in spec.columns() if c not in g.c]
    if missing:
        raise ValueError(f"Timeline {spec.key!r}: the grid's query has no column "
                         f"{', '.join(map(repr, missing))}")
    c = stmt.subquery("t")
    binds = grid_engine.binds(spec.source, user)
    s = c.c[spec.start]
    e = c.c[spec.end] if spec.end else None
    now = datetime.now(UTC).replace(tzinfo=None)

    extent = [func.min(s).label("lo"),
              (func.max(func.coalesce(e, s)) if e is not None else func.max(s)).label("hi")]
    if e is not None:
        extent.append(func.bool_or(e.is_(None)).label("open"))
    [ext] = grid_engine.read(db, select(*extent).where(s.is_not(None)), binds)
    aware = ext["lo"] is not None and ext["lo"].tzinfo is not None
    lo, hi = _utc(ext["lo"]), _utc(ext["hi"])
    if ext.get("open"):
        hi = max(hi, now) if hi else now

    conds = [s.is_not(None)]
    if start and end:
        def param(v):             # compare like with like: timestamptz columns get aware values
            return v.replace(tzinfo=UTC) if aware else v
        conds.append(s < param(end))
        # A bar overlaps the window if it ends after its start or is still going; a marker
        # (no end column, or its marker column true) only if it falls inside.
        inside = s >= param(start)
        if e is None:
            conds.append(inside)
        else:
            bar = or_(e.is_(None), e > param(start))
            conds.append(or_(and_(c.c[spec.marker].is_(True), inside),
                             and_(c.c[spec.marker].is_not(True), bar)) if spec.marker else bar)
    rows = grid_engine.read(db, select(c).where(and_(*conds)).order_by(s).limit(spec.limit + 1),
                            binds)

    lane_col = spec.source.column(spec.lane)
    tone_col = spec.source.column(spec.tone) if spec.tone else None
    lanes: dict[str, str] = {}
    bars = []
    for r in rows[:spec.limit]:
        lane = "" if r[spec.lane] is None else str(r[spec.lane])
        lanes.setdefault(lane, str(label_for(lane_col, lane)) if lane else "—")
        bars.append({
            "id": str(r.get("id", "")),
            "lane": lane,
            "start": iso(r[spec.start]),
            "end": iso(r[spec.end]) if spec.end else None,
            "label": fmt(spec.label, r),
            "tone": (tone_col.tones.get(str(r[spec.tone]), "") if tone_col else "") or "",
            "marker": bool(r[spec.marker]) if spec.marker else not spec.end,
            "href": fmt_url(spec.href, r) if spec.href else "",
        })
    order = list(lanes) if spec.lane_order == "start" else sorted(lanes)
    return {
        "extent": {"from": iso(lo), "to": iso(hi)},
        "window": {"from": iso(start) if start else iso(lo), "to": iso(end) if end else iso(hi)},
        "now": iso(now),
        "lanes": [{"key": k, "label": lanes[k]} for k in order],
        "bars": bars,
        "truncated": len(rows) > spec.limit,
    }
