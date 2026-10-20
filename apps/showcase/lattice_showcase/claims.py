"""Claims, copied from the claims system: the list across events, a claim's page with its
damage assessment and field reports, and the live intake simulator for the event underway.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

import geoengine
from lattice.api import (
    Action,
    ActionContext,
    ActionResult,
    Areas,
    ChartSpec,
    Column,
    Count,
    Db,
    DocumentKind,
    Filter,
    FormSpec,
    GridSpec,
    Highlight,
    HomeTile,
    Link,
    MapSpec,
    Palette,
    Panel,
    Permission,
    Points,
    RecordPage,
    Regions,
    Step,
    Sum,
    Time,
    TimelineSpec,
    TreeNode,
    View,
    build_chart,
    build_form,
    build_grid,
    build_map,
    build_timeline,
    csrf_protect,
    current_user,
    documents,
    flash,
    get_db,
    parse_form,
    render_grid_page,
    render_page,
    render_record_page,
    require,
    settings,
    sql_queries,
    transaction,
)
from lattice.api import (
    Field as InputField,
)
from lattice_showcase import cat_seed, places

SQL = sql_queries(Path(__file__).parent / "sql").claims
EVENTS = sql_queries(Path(__file__).parent / "sql").events
log = logging.getLogger(__name__)

MANAGE = "showcase.claims.manage"
PERMISSIONS = [Permission(MANAGE, "Handle claims",
                          "Assign claims to zones and surveyors, set priority, record "
                          "inspections, assessments and field reports, and run the intake "
                          "simulator.", default_roles=("editor",))]

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


def _options(query):
    return lambda db, user: [(str(r["id"]), r["label"]) for r in db.all(query)]


def assign_zone(ctx: ActionContext) -> str:
    ctx.db.run(SQL.assign_zone, ids=ctx.ids, zone_id=int(ctx.values["zone_id"]))
    return f"Moved {ctx.count} claim(s) to the zone."


def assign_surveyor(ctx: ActionContext) -> str:
    ctx.db.run(SQL.assign_surveyor, ids=ctx.ids, surveyor_id=int(ctx.values["surveyor_id"]))
    return f"Assigned {ctx.count} claim(s)."


def take(ctx: ActionContext) -> str:
    ctx.db.run(SQL.take, ids=ctx.ids, user_id=ctx.user.id)
    return f"You now handle {ctx.count} claim(s)."


def prioritise(ctx: ActionContext) -> str:
    ctx.db.run(SQL.prioritise, ids=ctx.ids, priority=True)
    return f"Flagged {ctx.count} claim(s) as priority."


def mark_inspected(ctx: ActionContext) -> str:
    ctx.db.run(SQL.mark_inspected, ids=ctx.ids)
    return f"Recorded the inspection of {ctx.count} claim(s)."


GRID = GridSpec(
    key="showcase.claims", title="Claims", path="/showcase/claims", query=SQL.grid,
    spatial=("lon", "lat"),
    columns=[
        Column("claim_number", "Claim", kind="mono", width="140px", required=True),
        Column("insured", "Insured", kind="strong", secondary="city", required=True),
        Column("event_code", "Event", kind="mono", width="100px"),
        Column("cause", "Cause", labels=dict(CAUSES), secondary="channel", width="120px"),
        Column("severity", "Severity", kind="badge", labels=dict(SEVERITIES),
               tones=SEVERITY_TONES, width="110px"),
        Column("status", "Status", kind="badge", labels=dict(STATUSES), tones=STATUS_TONES,
               width="110px"),
        Column("priority", "Priority", kind="bool", width="80px"),
        Column("zone", "Zone", width="170px"),
        Column("surveyor", "Surveyor", kind="user", width="150px"),
        Column("handler", "Handler", kind="user", width="150px"),
        Column("estimate", "Estimate", kind="money", align="right", width="120px"),
        Column("reported_at", "Reported", kind="ago", width="120px"),
        Column("days_after", "Day", kind="number", align="right", hidden=True),
        Column("channel", "Channel", labels=dict(CHANNELS), hidden=True),
        Column("city", "City", hidden=True),
        Column("county", "County", hidden=True),
        Column("line", "Line", labels={"homeowners": "Homeowners", "auto": "Auto",
                                       "commercial_property": "Commercial property"}, hidden=True),
        Column("location_ref", "Location", kind="mono", hidden=True),
    ],
    search=["claim_number", "insured", "policy_number", "city", "county", "zone", "surveyor",
            "handler"],
    filters=[Filter("status", "Status", STATUSES), Filter("severity", "Severity", SEVERITIES),
             Filter("event_code", "Event", lambda db, u: [(r["code"], f"{r['code']} · {r['name']}")
                                                           for r in db.all(EVENTS.grid)]),
             Filter("cause", "Cause", CAUSES), Filter("channel", "Channel", CHANNELS)],
    views=[View("open", "Open", where={"status": OPEN}),
           View("mine", "Mine", where={"handler_id": "$me", "status": OPEN}),
           View("waiting", "Waiting for a surveyor", where={"status": "new"}),
           View("priority", "Priority", where={"priority": True, "status": OPEN}),
           View("all", "All")],
    actions=[
        Action("open", "Open", scope="single", href="/showcase/claims/{id}", icon="external"),
        Action("assign_surveyor", "Assign surveyor", handler=assign_surveyor, icon="assign",
               permission=MANAGE, when={"status": OPEN},
               fields=[InputField("surveyor_id", "Surveyor", kind="select", required=True,
                                  options=_options(SQL.surveyor_options))]),
        Action("assign_zone", "Move to zone", handler=assign_zone, icon="showcase:map",
               permission=MANAGE, when={"status": OPEN},
               fields=[InputField("zone_id", "Zone", kind="select", required=True,
                                  options=_options(SQL.zone_options))]),
        Action("take", "Take", handler=take, icon="user", permission=MANAGE,
               when={"status": OPEN}),
        Action("prioritise", "Priority", handler=prioritise, icon="flag", permission=MANAGE,
               when={"priority": [False], "status": OPEN}),
        Action("inspected", "Inspected", handler=mark_inspected, icon="check", permission=MANAGE,
               when={"status": ["new", "assigned"]}, confirm="Record {count} inspection(s)?"),
    ],
    default_sort="-reported_at", row_href="/showcase/claims/{id}",
    palette=Palette("{claim_number} · {insured}", "/showcase/claims/{id}",
                    subtitle="{event_code} · {city}", icon="queue"),
    empty_title="No claims match", empty_text="Change the tab or clear the filters.",
)

TILES = [HomeTile("Claims waiting for a surveyor", GRID, view="waiting", tone="warning"),
         HomeTile("My open claims", GRID, view="mine", tone="accent")]


def event_footprint(db: Db, user, fixed: dict) -> dict:
    """The current footprint of the event the map is narrowed to (by id or code), if any."""
    event_id = (fixed.get("event_id") or [None])[0]
    code = (fixed.get("event_code") or [None])[0]
    found = (db.first(EVENTS.latest_footprint, event_id=int(event_id)) if str(event_id).isdigit()
             else db.first(EVENTS.latest_footprint_of, code=code) if code else None)
    return geoengine.as_geojson(db.conn, found["layer"]) if found else {"type": "FeatureCollection", "features": []}


MAP = MapSpec("showcase.claims_map", "Where claims are", GRID, height=460, search=places.find,
              layers=[
    Regions("county_fips", Count("Claims"), map="us-counties", title="By county"),
    Points("lon", "lat", color="severity", label="{claim_number}", title="Claims"),
    Areas("footprint", "Footprint", load=event_footprint, tone="danger"),
])
CHARTS = [
    ChartSpec("showcase.claims_since_landfall", "Claims per day since landfall, by event", GRID,
              "line", x="days_after", series="event_code", height=280, colors="categorical"),
    ChartSpec("showcase.claims_by_cause", "By cause", GRID, "doughnut", x="cause", height=280),
    ChartSpec("showcase.claims_estimate", "Estimated loss by severity", GRID, "bar", x="severity",
              y=Sum("estimate", "Estimated loss"), format="money", height=280,
              highlight=[Highlight(values=["total"], tone="danger")]),
    ChartSpec("showcase.claims_by_day", "Claims by day reported", GRID, "calendar",
              x=Time("reported_at", "day"), height=280),
]
EVENT_CHARTS = [
    ChartSpec("showcase.claims_per_day", "Claims per day", GRID, "bar",
              x=Time("reported_at", "day"), series="severity", stacked=True, height=260,
              colors="tones", drill="/showcase/claims"),
    ChartSpec("showcase.claims_calendar", "Claims calendar", GRID, "calendar",
              x=Time("reported_at", "day"), height=300, drill="/showcase/claims"),
    ChartSpec("showcase.claims_flow", "How claims came in, and where they stand", GRID, "sankey",
              x="channel", series="status", height=300),
]


def event_charts(request: Request, event_code: str) -> list[dict]:
    return [build_chart(request, c, linked=False, fixed={"event_code": event_code})
            for c in EVENT_CHARTS]


router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/claims")
def claims_page(request: Request, db: Db = Depends(get_db)):
    # ?x_event_code=CAT-2610 (from an event page, or a chart clicked there) narrows the
    # list, and the map and charts with it.
    return render_page(request, "showcase/claims.html", "claims.list",
                       grid=build_grid(request, db, GRID), map=build_map(request, MAP),
                       charts=[build_chart(request, c) for c in CHARTS])


# ── Damage assessments and field reports ─────────────────────────────────────

class Home(BaseModel):
    """A house or condo."""

    model_config = ConfigDict(title="Home")
    kind: Literal["home"] = "home"
    roof: Literal["none", "minor", "major", "destroyed"] = Field("none", title="Roof damage")
    interior_water: bool = Field(False, title="Water inside")
    water_line_in: float | None = Field(None, ge=0, title="Water line (inches above floor)")
    structural: bool = Field(False, title="Structural damage")
    habitable: bool = Field(True, title="Safe to live in")
    contents_damage_pct: int = Field(0, ge=0, le=100, title="Contents damaged (%)")


class Vehicle(BaseModel):
    """A car, truck or motorcycle."""

    model_config = ConfigDict(title="Vehicle")
    kind: Literal["vehicle"] = "vehicle"
    flood_line: Literal["none", "below_doors", "dashboard", "roof"] = Field("none", title="Flood line")
    airbags_deployed: bool = Field(False, title="Airbags deployed")
    drivable: bool = True
    total_loss_likely: bool = Field(False, title="Likely total loss")


class Commercial(BaseModel):
    """A shop, office, warehouse or restaurant."""

    model_config = ConfigDict(title="Commercial building")
    kind: Literal["commercial"] = "commercial"
    building_damage_pct: int = Field(0, ge=0, le=100, title="Building damaged (%)")
    stock_damaged: bool = Field(False, title="Stock or inventory damaged")
    days_closed: int = Field(0, ge=0, title="Days the business expects to be closed",
                             description="For business interruption")
    generator_on_site: bool = Field(False, title="Generator on site")


class Assessment(BaseModel):
    claim_number: str = Field(title="Claim", json_schema_extra={"readOnly": True})
    property: Home | Vehicle | Commercial = Field(discriminator="kind", title="What was inspected")
    damage_estimate: int = Field(ge=0, title="Repair estimate ($)")
    photos: int = Field(0, ge=0, title="Photos taken")
    notes: str = Field("", json_schema_extra={"x-widget": "textarea"})


ASSESSMENT = DocumentKind("showcase.assessment", "Damage assessment", schema=Assessment,
                          title="{claim_number}", edit=MANAGE)
REPORT = DocumentKind("showcase.field_report", "Field report", schema={"type": "object"},
                      title="{claim_number}: {summary}", edit=MANAGE)
REPORT_FORM = FormSpec("showcase.report_form", permission=MANAGE)        # no schema: free-form


def _assessment_for(db: Db, claim_number: str) -> dict | None:
    return next((d for d in documents.all_of(db, ASSESSMENT)
                 if d["data"].get("claim_number") == claim_number), None)


def _reports_for(db: Db, claim_number: str) -> list[dict]:
    return [d for d in documents.all_of(db, REPORT) if d["data"].get("claim_number") == claim_number]


REPORTS = GridSpec(
    key="showcase.field_report", title="Field reports", path="/showcase/field-reports",
    query=documents.QUERY, params={"kind": REPORT.key}, layout="split",
    columns=[Column("title", "Report", kind="strong", required=True),
             Column("updated_by", "From", kind="user", width="150px"),
             Column("updated_at", "Sent", kind="ago", width="110px")],
    search=["title"], default_sort="-updated_at", selection="none",
    panel=lambda db, user, row: {"template": "showcase/report_panel.html",
                                 "doc": documents.get(db, REPORT, row["id"])},
    panel_title="{title}", empty_title="No field reports yet",
    empty_text="Surveyors write them from a claim's page.",
)


# ── The claim page ───────────────────────────────────────────────────────────

def _lifecycle(request: Request, db: Db, row: dict) -> dict:
    order = [s for s, _ in STATUSES]
    at = order.index(row["status"])
    return {"steps": [Step(label, "done" if i < at or (i == at and key == "closed") else
                           "current" if i == at else "waiting")
                      for i, (key, label) in enumerate(STATUSES)]}


COVERAGES = {
    "homeowners": [("Dwelling (A)", 0.62), ("Other structures (B)", 0.06), ("Contents (C)", 0.22),
                   ("Loss of use (D)", 0.10)],
    "commercial_property": [("Building", 0.55), ("Business personal property", 0.25),
                            ("Business interruption", 0.20)],
    "auto": [("Comprehensive", 0.85), ("Rental reimbursement", 0.15)],
}


def _coverages(request: Request, db: Db, row: dict) -> dict:
    """The estimate split across the policy's coverages: an illustration, not adjusting."""
    claim = db.one(SQL.by_id, id=row["id"])
    nodes = []
    for name, share in COVERAGES[claim["line"]]:
        estimate = float(claim["estimate"]) * share
        paid = float(claim["paid"]) * share
        children = [TreeNode(f"Paid ${paid:,.0f}", tone="success", badge="Payment")] if paid else []
        nodes.append(TreeNode(name, note=f"estimate ${estimate:,.0f}", children=children))
    return {"nodes": [TreeNode(claim["claim_number"], badge=dict(STATUSES)[claim["status"]],
                               tone=STATUS_TONES[claim["status"]], children=nodes)]}


def _assessment(request: Request, db: Db, row: dict) -> dict:
    doc = _assessment_for(db, row["claim_number"])
    return {"doc": doc, "claim_id": row["id"], "can_edit": request.state.user.can(MANAGE)}


def _reports(request: Request, db: Db, row: dict) -> dict:
    return {"reports": _reports_for(db, row["claim_number"]), "claim_id": row["id"],
            "can_edit": request.state.user.can(MANAGE)}


def _where(request: Request, db: Db, row: dict) -> dict:
    return {"map": build_map(request, MAP, linked=False,
                             fixed={"id": row["id"], "event_id": row["event_id"]})}


PROGRESS = GridSpec(
    key="showcase.claim_progress", title="Claim progress", path="/showcase/claims",
    query=SQL.progress,
    columns=[Column("label", "Stage", kind="strong"),
             Column("lane", "Lane", labels={"claim": "Progress", "reports": "Field reports"}),
             Column("phase", "Phase", tones={"waiting": "warning", "surveyor": "info",
                                            "settling": "accent", "closing": "success",
                                            "report": "neutral"}),
             Column("starts_at", "From", kind="datetime"), Column("ends_at", "To", kind="datetime")],
    selection="none", export=False, views=[View("all", "All")],
)
TIMELINE = TimelineSpec(
    "showcase.claim_timeline", "Progress", PROGRESS, start="starts_at", end="ends_at",
    lane="lane", label="{label}", tone="phase", marker="is_marker", lane_order="lane")


def _progress(request: Request, db: Db, row: dict) -> dict:
    return {"timeline": build_timeline(request, TIMELINE, linked=False,
                                       fixed={"claim_id": row["id"]})}


DETAIL = RecordPage(
    grid=GRID, nav_key="claims.claim", title="{claim_number} · {insured}",
    subtitle="{event} · {city}", status="status", crumb="{claim_number}",
    reference_kind="showcase.claim",
    properties=["event_code", "cause", "severity", "priority", "estimate", "zone", "surveyor",
                "handler", "line", "location_ref", "reported_at"],
    links=[Link("Open in claims system", "/showcase/claims-system/{claim_number}", icon="external"),
           Link("Claims within 1 mile", "/showcase/claims?view=all&near={lon},{lat},1609&near_label={claim_number}",
                icon="pin"),
           Link("Locations within 5 miles",
                "/showcase/locations?near={lon},{lat},8047&near_label={claim_number}", icon="pin")],
    panels=[Panel("lifecycle", "Status", "showcase/event_lifecycle.html", load=_lifecycle),
            Panel("progress", "How long each stage took", "showcase/claim_progress.html",
                  load=_progress, flush=True),
            Panel("assessment", "Damage assessment", "showcase/claim_assessment.html",
                  load=_assessment),
            Panel("reports", "Field reports", "showcase/claim_reports.html", load=_reports),
            Panel("coverages", "Coverages and payments", "showcase/claim_coverages.html",
                  load=_coverages, place="side"),
            Panel("where", "Where", "showcase/event_map.html", load=_where, place="side",
                  flush=True)],
)


def _assessment_page(request, claim: dict, form, status_code=200):
    return render_page(request, "showcase/assessment.html", "claims.claim", form=form,
                       claim=claim, status_code=status_code, crumb=claim["claim_number"])


@router.get("/claims/{claim_id}/assessment", dependencies=[Depends(require(MANAGE))])
def assessment_page(claim_id: int, request: Request, db: Db = Depends(get_db)):
    claim = db.one(SQL.by_id, id=claim_id)
    doc = _assessment_for(db, claim["claim_number"])
    kind = {"auto": "vehicle", "commercial_property": "commercial"}.get(claim["line"], "home")
    data = doc["data"] if doc else {"claim_number": claim["claim_number"],
                                    "property": {"kind": kind},
                                    "damage_estimate": int(claim["estimate"])}
    return _assessment_page(request, claim, build_form(request, ASSESSMENT.form, data))


@router.post("/claims/{claim_id}/assessment", dependencies=[Depends(require(MANAGE))])
async def save_assessment(claim_id: int, request: Request, db: Db = Depends(get_db),
                          user=Depends(current_user)):
    claim = db.one(SQL.by_id, id=claim_id)
    result = parse_form(request, ASSESSMENT.form, await request.form())
    if not result.ok:
        return _assessment_page(request, claim, result.form, status_code=400)
    data = {**result.data, "claim_number": claim["claim_number"]}
    doc = _assessment_for(db, claim["claim_number"])
    if doc:
        documents.update(db, user, ASSESSMENT, doc["id"], data)
    else:
        documents.create(db, user, ASSESSMENT, data)
        db.run(SQL.mark_inspected, ids=[claim_id])
    response = RedirectResponse(f"/showcase/claims/{claim_id}", status_code=303)
    flash(response, request, "Assessment saved.")
    return response


@router.get("/claims/{claim_id}/report", dependencies=[Depends(require(MANAGE))])
def report_page(claim_id: int, request: Request, db: Db = Depends(get_db)):
    claim = db.one(SQL.by_id, id=claim_id)
    start = {"claim_number": claim["claim_number"], "summary": "", "observed": "",
             "people_on_site": 0, "access_ok": True}
    return render_page(request, "showcase/report.html", "claims.claim", claim=claim,
                       form=build_form(request, REPORT_FORM, start), crumb=claim["claim_number"])


@router.post("/claims/{claim_id}/report", dependencies=[Depends(require(MANAGE))])
async def save_report(claim_id: int, request: Request, db: Db = Depends(get_db),
                      user=Depends(current_user)):
    claim = db.one(SQL.by_id, id=claim_id)
    result = parse_form(request, REPORT_FORM, await request.form())
    if not result.ok or not isinstance(result.data, dict):
        return render_page(request, "showcase/report.html", "claims.claim", claim=claim,
                           form=result.form, status_code=400, crumb=claim["claim_number"])
    documents.create(db, user, REPORT, {**result.data, "claim_number": claim["claim_number"]})
    response = RedirectResponse(f"/showcase/claims/{claim_id}", status_code=303)
    flash(response, request, "Field report sent.")
    return response


@router.get("/field-reports")
def reports_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, REPORTS, "claims.reports",
                            subtitle="Free-form reports from the field: no two are alike.")


@router.get("/claims-system/{claim_number}")
def claims_system(claim_number: str, request: Request):
    return render_page(request, "showcase/claims_system.html", "claims.list",
                       claim_number=claim_number, crumb=claim_number)


# ── Live intake: a simulator for the event underway ──────────────────────────

def _intake_set(ctx: ActionContext, running: bool, per_minute: int | None = None) -> ActionResult:
    current = ctx.db.one(SQL.intake)
    ctx.db.run(SQL.set_intake, running=running, per_minute=per_minute or current["per_minute"])
    return ActionResult("Intake started." if running else "Intake paused.",
                        redirect="/showcase/intake")


INTAKE_ACTIONS = [
    Action("start", "Start intake", scope="none", tone="primary", icon="play", permission=MANAGE,
           handler=lambda ctx: _intake_set(ctx, True, int(ctx.values["per_minute"])),
           fields=[InputField("per_minute", "Claims a minute", kind="select", default="30",
                              options=[("10", "10 a minute"), ("30", "30 a minute"),
                                       ("120", "120 a minute: a surge")])]),
    Action("pause", "Pause", scope="none", icon="stop", permission=MANAGE,
           handler=lambda ctx: _intake_set(ctx, False)),
]
INTAKE = GridSpec(
    key="showcase.intake", title="Live intake", path="/showcase/intake", query=SQL.grid,
    columns=[c for c in GRID.columns if c.key in ("claim_number", "insured", "cause", "severity",
                                                   "channel", "zone", "estimate", "reported_at")],
    actions=INTAKE_ACTIONS, poll_seconds=3, default_sort="-reported_at", selection="none",
    row_href="/showcase/claims/{id}", views=[View("all", "All")], export=False,
)
INTAKE_CHART = ChartSpec("showcase.intake_per_hour", "Claims per hour", INTAKE, "bar",
                         x=Time("reported_at", "hour"), series="severity", stacked=True,
                         height=220, colors="tones")


@router.get("/intake")
def intake_page(request: Request, db: Db = Depends(get_db)):
    event = db.first(SQL.live_event)
    fixed = {"event_id": event["id"]} if event else {"event_id": 0}
    return render_page(request, "showcase/intake.html", "claims.intake", event=event,
                       intake=db.one(SQL.intake),
                       grid=build_grid(request, db, INTAKE, fixed=fixed),
                       per_hour=build_chart(request, INTAKE_CHART, linked=False, fixed=fixed))


def simulate_intake(rng: random.Random, seconds: float) -> int:
    """Add the claims the simulator would have received in `seconds`. Returns how many."""
    with transaction() as db:
        control = db.one(SQL.intake)
        event = db.first(SQL.live_event)
        if not control["running"] or event is None:
            return 0
        expected = control["per_minute"] * seconds / 60
        count = int(expected) + (1 if rng.random() < expected % 1 else 0)
        candidates = db.all(SQL.intake_candidates, event_id=event["id"], limit=count)
        zones = [z["id"] for z in db.all(SQL.zones_of, event_id=event["id"])]
        number = db.value(SQL.next_claim_number)
        now = datetime.now(UTC).replace(tzinfo=None)
        spec = cat_seed.EVENTS[-1]
        rows = []
        for i, loc in enumerate(candidates):
            severity = cat_seed.weighted(rng, spec["severity"])
            lo, hi = cat_seed.SEVERITY_SHARE[severity]
            rows.append(dict(
                claim_number=f"CLM-{now:%y}-{number + i:06d}", event_id=event["id"],
                location_id=loc["id"], loss_date=now.date() - timedelta(days=1), reported_at=now,
                channel=cat_seed.weighted(rng, cat_seed.CHANNEL),
                cause=cat_seed.weighted(rng, spec["causes"]), severity=severity, status="new",
                priority=False, estimate=round(float(loc["tiv"]) * rng.uniform(lo, hi), -2), paid=0,
                zone_id=rng.choice(zones) if zones else None, surveyor_id=None, adjuster_id=None,
                assigned_at=None, inspected_at=None, settled_at=None, closed_at=None,
                updated_at=now))
        db.run_many(cat_seed.SQL.add_claim, rows)
        return len(rows)


async def background() -> None:
    """Started with the host: the intake simulator, every 3 s (development only)."""
    if settings.app_env != "development":
        return
    rng = random.Random()
    while True:
        try:
            await run_in_threadpool(simulate_intake, rng, 3)
        except Exception:
            log.exception("Intake simulator failed")
        await asyncio.sleep(3)


# Declared after the routes above, which it would otherwise swallow.
@router.get("/claims/{claim_id}")
def claim_page(claim_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, DETAIL, claim_id)
