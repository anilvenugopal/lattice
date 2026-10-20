"""Catastrophe events: the list, the event page, and declaring an event.

An event's footprint (the affected area) comes in versions: forecast advisories, perimeter
updates, a redrawn evacuation zone. Each version is a geoengine layer, and an exposure run
records which insured locations it covers.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

import geoengine
from lattice.api import (
    Action,
    ActionContext,
    Column,
    Db,
    FormSpec,
    GridSpec,
    Link,
    Palette,
    Panel,
    Permission,
    RecordPage,
    Step,
    View,
    audit,
    build_form,
    csrf_protect,
    current_user,
    flash,
    get_db,
    parse_form,
    render_grid_page,
    render_page,
    render_record_page,
    require,
    sql_queries,
)

SQL = sql_queries(Path(__file__).parent / "sql").events
MANAGE = "showcase.events.manage"
PERMISSIONS = [Permission(MANAGE, "Manage catastrophe events",
                          "Declare events, add footprint versions, run exposure and move "
                          "events through their stages.", default_roles=("editor",))]

PERILS = [("hurricane", "Hurricane"), ("hail", "Hail"), ("wildfire", "Wildfire"),
          ("freeze", "Freeze")]
PERIL_TONES = {"hurricane": "danger", "hail": "info", "wildfire": "warning", "freeze": "accent"}
STAGES = [("watch", "Watch"), ("landfall", "Landfall"), ("response", "Response"),
          ("recovery", "Recovery"), ("closed", "Closed")]
STAGE_TONES = {"watch": "info", "landfall": "danger", "response": "warning",
               "recovery": "accent", "closed": "neutral"}
DETAIL_LABELS = {"category": "Category", "max_wind_mph": "Maximum wind (mph)",
                 "pressure_mb": "Central pressure (mb)", "landfall": "Landfall",
                 "storm_surge_ft": "Storm surge (ft)", "hail_size_in": "Hail size (in)",
                 "acres_burned": "Acres burned", "containment_pct": "Containment (%)",
                 "structures_destroyed": "Structures destroyed", "min_temp_f": "Lowest temperature (°F)",
                 "hours_below_freezing": "Hours below freezing", "power_outages": "Power outages"}


def advance(ctx: ActionContext) -> str:
    ctx.db.run(SQL.advance, ids=ctx.ids)
    return f"Moved {ctx.count} event(s) to the next stage."


GRID = GridSpec(
    key="showcase.events", title="Events", path="/showcase/events", query=SQL.grid,
    columns=[
        Column("code", "Code", kind="mono", width="100px", required=True),
        Column("name", "Event", kind="strong", secondary="region", required=True),
        Column("region", "Region", hidden=True),
        Column("peril", "Peril", kind="badge", labels=dict(PERILS), tones=PERIL_TONES, width="110px"),
        Column("status", "Stage", kind="badge", labels=dict(STAGES), tones=STAGE_TONES, width="110px"),
        Column("starts_on", "Began", kind="date", width="110px"),
        Column("exposed_tiv", "Exposed value", kind="money", align="right", width="140px"),
        Column("claims", "Claims", kind="number", align="right", width="90px"),
        Column("open_claims", "Open", kind="number", align="right", width="80px"),
        Column("incurred", "Estimated loss", kind="money", align="right", width="140px"),
        Column("pcs_code", "PCS code", kind="mono", hidden=True),
    ],
    search=["code", "name", "region", "pcs_code"],
    views=[View("active", "Active", where={"status": ["watch", "landfall", "response", "recovery"]}),
           View("closed", "Closed", where={"status": "closed"}), View("all", "All")],
    actions=[Action("new", "Declare event", scope="none", href="/showcase/events/new",
                    tone="primary", icon="plus", permission=MANAGE),
             Action("open", "Open", scope="single", href="/showcase/events/{id}", icon="external"),
             Action("advance", "Next stage", handler=advance, icon="chevron-right", permission=MANAGE,
                    when={"status": ["watch", "landfall", "response", "recovery"]},
                    confirm="Move {count} event(s) to their next stage?")],
    default_sort="-starts_on", row_href="/showcase/events/{id}",
    palette=Palette("{code} · {name}", "/showcase/events/{id}", subtitle="{region}",
                    icon="showcase:storm"),
    empty_title="No events", empty_text="Declare one when a catastrophe threatens the book.",
)

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/events")
def events_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "events.list",
                            subtitle="Catastrophes the carrier is responding to, or has.")


# ── The event page ───────────────────────────────────────────────────────────

def _lifecycle(request: Request, db: Db, row: dict) -> dict:
    order = [s for s, _ in STAGES]
    at = order.index(row["status"])
    notes = {"watch": row["starts_on"], "landfall": row["landfall_on"], "closed": row["closed_on"]}
    steps = []
    for i, (key, label) in enumerate(STAGES):
        state = "done" if i < at or (i == at and key == "closed") else "current" if i == at else "waiting"
        when = notes.get(key)
        steps.append(Step(label, state, when.strftime("%b %d, %Y") if when else ""))
    return {"steps": steps}


def _details(request: Request, db: Db, row: dict) -> dict:
    return {"items": [(DETAIL_LABELS.get(k, k.replace("_", " ").capitalize()), v)
                      for k, v in (row["details"] or {}).items()]}


def _footprints(request: Request, db: Db, row: dict) -> dict:
    return {"versions": db.all(SQL.footprints, event_id=row["id"]),
            "can_manage": request.state.user.can(MANAGE)}


def _exposure_map(request: Request, db: Db, row: dict) -> dict:
    from lattice_showcase import exposure
    return {"map": exposure.event_map(request, row["id"])}


def _claims_charts(request: Request, db: Db, row: dict) -> dict:
    from lattice_showcase import claims
    return {"charts": claims.event_charts(request, row["code"])}


DETAIL = RecordPage(
    grid=GRID, nav_key="events.event", title="{name}", subtitle="{code} · {region}",
    status="status", crumb="{code}", reference_kind="showcase.event",
    properties=["peril", "status", "starts_on", "pcs_code", "exposed_tiv", "claims",
                "open_claims", "incurred"],
    details_title="At a glance",
    links=[Link("Exposure", "/showcase/events/{id}/exposure", icon="showcase:map"),
           Link("Claims", "/showcase/claims?x_event_code={code}", icon="queue"),
           Link("Loss estimate", "/showcase/events/{id}/loss", icon="showcase:chart")],
    panels=[Panel("lifecycle", "Stage", "showcase/event_lifecycle.html", load=_lifecycle),
            Panel("details", "The event", "showcase/event_details.html", load=_details),
            Panel("footprints", "Footprint versions", "showcase/event_footprints.html",
                  load=_footprints, place="side"),
            Panel("map", "Exposure inside the footprint", "showcase/event_map.html",
                  load=_exposure_map, place="full", flush=True),
            Panel("claims", "Claims as they arrived", "showcase/event_claims.html",
                  load=_claims_charts, place="full", flush=True)],
)


# ── Declaring an event ───────────────────────────────────────────────────────

class Hurricane(BaseModel):
    """A tropical storm or hurricane, from National Hurricane Center advisories."""

    peril: Literal["hurricane"] = "hurricane"
    category: int = Field(1, ge=1, le=5, description="Saffir–Simpson category, 1 to 5")
    max_wind_mph: int = Field(ge=39, le=200, title="Maximum sustained wind (mph)")
    pressure_mb: int | None = Field(None, ge=880, le=1020, title="Central pressure (mb)")
    landfall: str = Field("", title="Expected landfall", description="e.g. Near Cameron, Louisiana")


class Hail(BaseModel):
    """A severe convective storm with hail."""

    peril: Literal["hail"] = "hail"
    hail_size_in: float = Field(ge=0.25, le=6, title="Largest hail (inches)")
    max_wind_mph: int | None = Field(None, ge=0, le=150, title="Maximum wind (mph)")


class Wildfire(BaseModel):
    """A wildfire, from fire agency perimeter updates."""

    peril: Literal["wildfire"] = "wildfire"
    acres_burned: int = Field(ge=0, title="Acres burned")
    containment_pct: int = Field(0, ge=0, le=100, title="Containment (%)")


class Freeze(BaseModel):
    """A winter storm or hard freeze."""

    peril: Literal["freeze"] = "freeze"
    min_temp_f: int = Field(ge=-40, le=40, title="Lowest temperature (°F)")
    hours_below_freezing: int = Field(ge=0, title="Hours below freezing")


class ByCounties(BaseModel):
    """Counties under a warning: the simplest footprint."""

    model_config = ConfigDict(title="Counties under a warning")
    source: Literal["counties"] = "counties"
    state: Literal["TX", "LA", "FL", "CA"] = "TX"
    counties: str = Field(min_length=3, description="Names, separated by commas: Harris, Galveston, Brazoria")


class ByFile(BaseModel):
    """A shape from outside: an NHC forecast cone or a fire perimeter, as GeoJSON."""

    model_config = ConfigDict(title="A GeoJSON file")
    source: Literal["upload"] = "upload"
    geojson: str = Field(title="GeoJSON file", json_schema_extra={"x-widget": "file",
                                                                  "x-accept": ".geojson,.json"})


class BySavedArea(BaseModel):
    """An area drawn and saved on the Locations map."""

    model_config = ConfigDict(title="An area saved on the Locations map")
    source: Literal["area"] = "area"
    area: str = Field(title="Saved area", description="The name it was saved under")


class DeclareEvent(BaseModel):
    name: str = Field(min_length=3, title="Event name", description="e.g. Hurricane Delta")
    region: str = Field("", description="e.g. Gulf Coast")
    starts_on: date = Field(title="Watch began")
    peril: Hurricane | Hail | Wildfire | Freeze = Field(discriminator="peril", title="Peril")
    footprint: ByCounties | ByFile | BySavedArea = Field(discriminator="source",
                                                         title="Affected area")


DECLARE = FormSpec("showcase.declare_event", schema=DeclareEvent, permission=MANAGE, json_tab=False,
                   ui={"": {"sections": [("The event", ["name", "region", "starts_on", "peril"]),
                                         ("Footprint", ["footprint"])]},
                       "footprint/counties": {"widget": "textarea"}})


class FootprintError(ValueError):
    """The footprint can't be made: unknown counties, a file that isn't a shape…"""


def footprint_shapes(db: Db, given: dict) -> dict:
    """The footprint as a GeoJSON FeatureCollection, from counties, a file or a saved area."""
    if given["source"] == "counties":
        wanted = {n.strip().lower().removesuffix(" county") for n in given["counties"].split(",") if n.strip()}
        fips = {r["county_fips"] for r in db.all(SQL.county_list)
                if r["state"] == given["state"] and r["county"].lower() in wanted}
        found = {r["county"].lower() for r in db.all(SQL.county_list)
                 if r["state"] == given["state"] and r["county_fips"] in fips}
        if missing := wanted - found:
            raise FootprintError(f"No insured locations in: {', '.join(sorted(missing))} ({given['state']})")
        counties = geoengine.as_geojson(db.conn, "us-counties")
        return {"type": "FeatureCollection",
                "features": [f for f in counties["features"] if f["id"] in fips]}
    if given["source"] == "upload":
        try:
            shapes = json.loads(given["geojson"])
        except ValueError:
            raise FootprintError("The file is not GeoJSON.") from None
        if shapes.get("type") == "Feature":
            shapes = {"type": "FeatureCollection", "features": [shapes]}
        if shapes.get("type") in ("Polygon", "MultiPolygon"):
            shapes = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": shapes}]}
        if shapes.get("type") != "FeatureCollection" or not shapes.get("features"):
            raise FootprintError("The file has no shapes (a GeoJSON polygon or FeatureCollection).")
        return shapes
    area = db.first(SQL.area_by_name, name=given["area"])
    if area is None:
        raise FootprintError(f"No saved area named {given['area']!r}.")
    return geoengine.as_geojson(db.conn, area["layer"])


def add_footprint(db: Db, event_id: int, label: str, source: str, shapes: dict) -> int:
    """A new footprint version from shapes, stored as a geoengine layer, with an exposure run
    queued for it. Returns the footprint id."""
    row = db.first(SQL.add_footprint, event_id=event_id, label=label, source=source, layer="")
    layer = f"event-{event_id}-v{row['version']}"
    layer_id = geoengine.create_layer(db.conn, layer, "areas", label)
    geoengine.put_geojson(db.conn, layer_id, shapes)
    db.run(SQL.set_footprint_layer, id=row["id"], layer=layer)
    db.value(SQL.queue_exposure, event_id=event_id, footprint_id=row["id"])
    return row["id"]


@router.get("/events/new", dependencies=[Depends(require(MANAGE))])
def declare_page(request: Request, db: Db = Depends(get_db)):
    form = build_form(request, DECLARE, {"starts_on": date.today().isoformat(),
                                          "peril": {"peril": "hurricane"},
                                          "footprint": {"source": "counties", "state": "TX"}})
    return render_page(request, "showcase/declare_event.html", "events.new", form=form,
                       areas=db.all(SQL.areas))


@router.post("/events/new", dependencies=[Depends(require(MANAGE))])
async def declare(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    result = parse_form(request, DECLARE, await request.form())
    shapes = None
    if result.ok:
        try:
            shapes = footprint_shapes(db, result.data["footprint"])
        except FootprintError as exc:
            result.form["general"] = [str(exc)]
    if shapes is None:
        return render_page(request, "showcase/declare_event.html", "events.new",
                           form=result.form, areas=db.all(SQL.areas), status_code=400)
    data = result.data
    peril = {k: v for k, v in data["peril"].items() if k != "peril" and v not in (None, "")}
    event_id = db.value(SQL.create, name=data["name"], peril=data["peril"]["peril"],
                        region=data["region"], starts_on=data["starts_on"], details=peril)
    source = data["footprint"]["source"]
    add_footprint(db, event_id, {"counties": "Counties under warning", "upload": "Uploaded shape",
                                 "area": f"Saved area: {data['footprint'].get('area', '')}"}[source],
                  source, shapes)
    audit.record(db, user.id, "showcase.events.declared", f"Declared {data['name']}",
                 "showcase.events", event_id)
    response = RedirectResponse(f"/showcase/events/{event_id}", status_code=303)
    flash(response, request, "Event declared. Its exposure run is queued.")
    return response


# Declared after /events/new, which it would otherwise swallow.
@router.get("/events/{event_id}")
def event_page(event_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, DETAIL, event_id)
