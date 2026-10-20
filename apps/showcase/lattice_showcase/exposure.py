"""Exposure: which insured locations an event's footprint covers, and how much value.

A footprint version gets an exposure run: the app's background task matches the locations
inside it, one state at a time, so its progress shows. (In production this is a Taskline job.)
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import geoengine
from lattice.api import (
    Areas,
    ChartSpec,
    Column,
    Db,
    Filter,
    FormSpec,
    GridSpec,
    Hexagons,
    Highlight,
    MapSpec,
    Points,
    Regions,
    Sum,
    View,
    build_chart,
    build_form,
    build_grid,
    build_map,
    csrf_protect,
    flash,
    get_db,
    parse_form,
    render_page,
    require,
    settings,
    sql_queries,
    transaction,
)
from lattice_showcase import events, places

SQL = sql_queries(Path(__file__).parent / "sql").exposure
EVENTS = sql_queries(Path(__file__).parent / "sql").events
log = logging.getLogger(__name__)

LINES = [("homeowners", "Homeowners"), ("commercial_property", "Commercial property"), ("auto", "Auto")]
CONSTRUCTION = [("frame", "Wood frame"), ("masonry", "Masonry"), ("steel", "Steel"),
                ("manufactured", "Manufactured home"), ("vehicle", "Vehicle")]
TIERS = [("rooftop", "Rooftop"), ("parcel", "Parcel"), ("street", "Street"),
         ("zip", "Zip centroid"), ("county", "County centroid")]
TIER_TONES = {"rooftop": "success", "parcel": "info", "street": "neutral", "zip": "warning",
              "county": "danger"}
RUN_STATUSES = [("queued", "Queued"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")]
RUN_TONES = {"queued": "neutral", "running": "info", "done": "success", "failed": "danger"}


def location_columns() -> list[Column]:
    """The columns of a list of locations, shared with the Locations page."""
    return [Column("ref", "Location", kind="mono", width="110px", required=True),
            Column("insured", "Insured", kind="strong", secondary="city", required=True),
            Column("line", "Line", labels=dict(LINES), width="150px"),
            Column("construction", "Construction", labels=dict(CONSTRUCTION), width="140px"),
            Column("occupancy", "Occupancy", hidden=True),
            Column("county", "County", width="130px"),
            Column("state", "State", width="70px"),
            Column("tiv", "Insured value", kind="money", align="right", width="130px"),
            Column("deductible", "Deductible", kind="money", align="right", hidden=True),
            Column("quality", "Location quality", kind="badge", labels=dict(TIERS),
                   tones=TIER_TONES, width="140px"),
            Column("year_built", "Built", kind="number", hidden=True),
            Column("policy_number", "Policy", kind="mono", hidden=True),
            Column("city", "City", hidden=True)]


GRID = GridSpec(
    key="showcase.exposure", title="Exposed locations", path="/showcase/events",
    query=SQL.grid, columns=location_columns(), spatial=("lon", "lat"),
    search=["ref", "insured", "policy_number", "city", "county"],
    filters=[Filter("line", "Line", LINES), Filter("construction", "Construction", CONSTRUCTION),
             Filter("quality", "Location quality", TIERS), Filter("state", "State",
             [("TX", "Texas"), ("LA", "Louisiana"), ("FL", "Florida"), ("CA", "California")])],
    default_sort="-tiv", empty_title="Nothing exposed",
    empty_text="The footprint covers no insured locations, or its exposure run hasn't finished.",
)


def footprint(db: Db, user, fixed: dict) -> dict:
    """The event's current footprint, for the map."""
    event_id = (fixed.get("event_id") or [None])[0]
    found = db.first(EVENTS.latest_footprint, event_id=int(event_id)) if event_id else None
    return geoengine.as_geojson(db.conn, found["layer"]) if found else {"type": "FeatureCollection", "features": []}


MAP = MapSpec("showcase.exposure_map", "Exposed value", GRID, format="money", height=520, search=places.find,
              layers=[
    Regions("county_fips", Sum("tiv", "Exposed value"), map="us-counties", title="By county"),
    Hexagons("h3_7", Sum("tiv", "Exposed value"), title="Concentration"),
    Points("lon", "lat", color="quality", label="{ref}", title="Locations"),
    Areas("footprint", "Footprint", load=footprint, tone="danger"),
])
CHARTS = [
    ChartSpec("showcase.exposure_by_line", "Exposed value by line and construction", GRID,
              "treemap", x="construction", series="line", y=Sum("tiv", "Insured value"),
              format="money", height=300),
    ChartSpec("showcase.exposure_by_county", "Top counties", GRID, "bar", x="county",
              y=Sum("tiv", "Insured value"), format="money", horizontal=True, limit=8, height=300),
    ChartSpec("showcase.exposure_quality", "How precisely we know where they are", GRID,
              "doughnut", x="quality", height=300,
              # Zip and county centroids: too rough to say whether a location is inside.
              highlight=[Highlight(values=["zip", "county"], tone="warning")]),
]
RUNS = GridSpec(
    key="showcase.exposure_runs", title="Exposure runs", path="/showcase/exposure-runs",
    query=SQL.runs, poll_seconds=2, selection="none",
    columns=[Column("id", "#", kind="mono", width="60px"),
             Column("event", "Event", kind="strong", secondary="footprint"),
             Column("footprint", "Footprint", hidden=True),
             Column("status", "Status", kind="badge", labels=dict(RUN_STATUSES), tones=RUN_TONES,
                    width="110px"),
             Column("progress", "Progress", kind="progress", width="150px"),
             Column("locations", "Locations", kind="number", align="right", width="110px"),
             Column("tiv", "Exposed value", kind="money", align="right", width="140px"),
             Column("finished_at", "Finished", kind="ago", width="120px")],
    views=[View("all", "All")], default_sort="-id", export=False,
    empty_title="No exposure runs yet",
)

router = APIRouter(dependencies=[Depends(csrf_protect)])


def event_map(request: Request, event_id: int) -> dict:
    return build_map(request, MAP, linked=False, fixed={"event_id": event_id})


class NewFootprint(BaseModel):
    label: str = Field(min_length=2, title="Version label", description="e.g. Advisory 19, 18 Oct")
    footprint: events.ByCounties | events.ByFile | events.BySavedArea = Field(
        discriminator="source", title="Affected area")


FOOTPRINT_FORM = FormSpec("showcase.new_footprint", schema=NewFootprint, permission=events.MANAGE,
                          json_tab=False, ui={"footprint/counties": {"widget": "textarea"}})


def _page(request: Request, db: Db, event_id: int, form=None, status_code: int = 200):
    fixed = {"event_id": event_id}
    grid = build_grid(request, db, GRID, fixed=fixed)
    return render_page(
        request, "showcase/exposure.html", "events.exposure", status_code=status_code,
        event=db.one(EVENTS.by_id, id=event_id),
        footprint=db.first(EVENTS.latest_footprint, event_id=event_id), grid=grid, map=build_map(request, MAP, fixed=fixed),
        charts=[build_chart(request, c, fixed=fixed) for c in CHARTS],
        runs=build_grid(request, db, RUNS, sync_url=False, fixed={"event_id": event_id}),
        form=form or build_form(request, FOOTPRINT_FORM, {"footprint": {"source": "upload"}}),
        can_manage=request.state.user.can(events.MANAGE), crumb="Exposure")


@router.get("/events/{event_id}/exposure")
def exposure_page(event_id: int, request: Request, db: Db = Depends(get_db)):
    return _page(request, db, event_id)


@router.post("/events/{event_id}/footprints", dependencies=[Depends(require(events.MANAGE))])
async def add_version(event_id: int, request: Request, db: Db = Depends(get_db)):
    result = parse_form(request, FOOTPRINT_FORM, await request.form())
    shapes = None
    if result.ok:
        try:
            shapes = events.footprint_shapes(db, result.data["footprint"])
        except events.FootprintError as exc:
            result.form["general"] = [str(exc)]
    if shapes is None:
        return _page(request, db, event_id, form=result.form, status_code=400)
    events.add_footprint(db, event_id, result.data["label"], result.data["footprint"]["source"],
                         shapes)
    response = RedirectResponse(f"/showcase/events/{event_id}/exposure", status_code=303)
    flash(response, request, "New footprint version added; its exposure run is queued.")
    return response


# ── Running exposure ─────────────────────────────────────────────────────────

def process_next(pause: float = 0.0) -> bool:
    """Run the oldest queued exposure run, one state at a time. Returns False if none."""
    with transaction() as db:
        run = db.first(SQL.next_queued)
    if run is None:
        return False
    with transaction() as db:
        layer = db.value(SQL.footprint_layer, id=run["footprint_id"])
        states = [r["state"] for r in db.all(SQL.states_in, layer=layer)]
    for i, state in enumerate(states, start=1):
        with transaction() as db:
            db.run(SQL.add_state, run_id=run["id"], layer=layer, state=state)
            db.run(SQL.progress, id=run["id"], progress=5 + int(90 * i / len(states)))
        time.sleep(pause)                    # paced, so the list shows the run moving
    with transaction() as db:
        db.run(SQL.finish, id=run["id"])
    return True


async def background() -> None:
    """Started with the host: run queued exposure runs every 2 s (development only)."""
    if settings.app_env != "development":
        return
    while True:
        try:
            while await run_in_threadpool(process_next, 1.0):
                pass
        except Exception:
            log.exception("Exposure run failed")
        await asyncio.sleep(2)

