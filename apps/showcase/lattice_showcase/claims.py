"""Claims, copied from the claims system: lists across events, and an event's claims charts."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from lattice.api import (
    ChartSpec,
    Column,
    Db,
    Filter,
    GridSpec,
    Time,
    View,
    build_chart,
    get_db,
    render_grid_page,
    sql_queries,
)

SQL = sql_queries(Path(__file__).parent / "sql").claims

STATUSES = [("new", "New"), ("assigned", "Assigned"), ("inspected", "Inspected"),
            ("settled", "Settled"), ("closed", "Closed")]
STATUS_TONES = {"new": "info", "assigned": "accent", "inspected": "warning", "settled": "success",
                "closed": "neutral"}
SEVERITIES = [("minor", "Minor"), ("moderate", "Moderate"), ("major", "Major"), ("total", "Total loss")]
SEVERITY_TONES = {"minor": "neutral", "moderate": "info", "major": "warning", "total": "danger"}
CHANNELS = [("phone", "Phone"), ("app", "Mobile app"), ("agent", "Agent"), ("web", "Web")]
CAUSES = [("wind", "Wind"), ("storm_surge", "Storm surge"), ("flood", "Flood"),
          ("tree_fall", "Fallen tree"), ("hail", "Hail"), ("fire", "Fire"), ("smoke", "Smoke"),
          ("evacuation", "Evacuation"), ("frozen_pipes", "Frozen pipes"),
          ("roof_collapse", "Roof collapse"), ("power_surge", "Power surge")]
OPEN = ["new", "assigned", "inspected"]

GRID = GridSpec(
    key="showcase.claims", title="Claims", path="/showcase/claims", query=SQL.grid,
    spatial=("lon", "lat"),
    columns=[
        Column("claim_number", "Claim", kind="mono", width="140px", required=True),
        Column("insured", "Insured", kind="strong", secondary="city", required=True),
        Column("event_code", "Event", kind="mono", width="100px"),
        Column("cause", "Cause", labels=dict(CAUSES), width="120px"),
        Column("severity", "Severity", kind="badge", labels=dict(SEVERITIES),
               tones=SEVERITY_TONES, width="110px"),
        Column("status", "Status", kind="badge", labels=dict(STATUSES), tones=STATUS_TONES,
               width="110px"),
        Column("priority", "Priority", kind="bool", width="80px"),
        Column("zone", "Zone", width="160px"),
        Column("surveyor", "Surveyor", kind="user", width="150px"),
        Column("estimate", "Estimate", kind="money", align="right", width="120px"),
        Column("reported_at", "Reported", kind="ago", width="120px"),
        Column("channel", "Channel", labels=dict(CHANNELS), hidden=True),
        Column("city", "City", hidden=True),
        Column("county", "County", hidden=True),
        Column("line", "Line", hidden=True),
    ],
    search=["claim_number", "insured", "policy_number", "city", "county", "zone"],
    filters=[Filter("status", "Status", STATUSES), Filter("severity", "Severity", SEVERITIES),
             Filter("cause", "Cause", CAUSES), Filter("channel", "Channel", CHANNELS)],
    views=[View("open", "Open", where={"status": OPEN}), View("all", "All")],
    default_sort="-reported_at", row_href="/showcase/claims/{id}",
)

EVENT_CHARTS = [
    ChartSpec("showcase.claims_per_day", "Claims per day", GRID, "bar",
              x=Time("reported_at", "day"), series="severity", stacked=True, height=260),
    ChartSpec("showcase.claims_calendar", "Claims calendar", GRID, "calendar",
              x=Time("reported_at", "day"), height=300),
    ChartSpec("showcase.claims_flow", "How claims came in, and where they stand", GRID, "sankey",
              x="channel", series="status", height=300),
]


def event_charts(request: Request, event_id: int) -> list[dict]:
    return [build_chart(request, c, linked=False, fixed={"event_id": event_id})
            for c in EVENT_CHARTS]


router = APIRouter()


@router.get("/claims")
def claims_page(request: Request, db: Db = Depends(get_db)):
    # ?x_event_id=4 (from an event page) fixes the list to one event.
    return render_grid_page(request, db, GRID, "claims.list",
                            subtitle="Copied from the claims system every few minutes.")
