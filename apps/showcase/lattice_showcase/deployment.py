"""Deployment: who is working where on the live event, as a graph.

The event, its zones and their leads, and the surveyors in each zone with their claims.
Select a zone to act on its waiting claims; select a surveyor to open their claims.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request

from lattice.api import (
    Action,
    ActionContext,
    Column,
    Db,
    Graph,
    GraphEdge,
    GraphNode,
    GridSpec,
    TimelineSpec,
    build_graph,
    build_timeline,
    get_db,
    render_page,
    sql_queries,
)
from lattice_showcase import claims
from lattice_showcase.claims import MANAGE

SQL = sql_queries(Path(__file__).parent / "sql").claims


def prioritise_zone(ctx: ActionContext) -> str:
    ctx.db.run(SQL.prioritise_zone, ids=ctx.ids)
    return f"Flagged every waiting claim in {ctx.count} zone(s) as priority."


ZONES = GridSpec(
    key="showcase.zones", title="Zones", path="/showcase/deployment", query=SQL.zones_grid,
    columns=[Column("name", "Zone", kind="strong"), Column("event_code", "Event", kind="mono"),
             Column("open_claims", "Open claims", kind="number"),
             Column("waiting", "Waiting", kind="number")],
    actions=[Action("prioritise", "Prioritise waiting claims", handler=prioritise_zone,
                    icon="flag", permission=MANAGE,
                    confirm="Flag every waiting claim in this zone as priority?")],
)

# Each surveyor's inspection visits; the gaps between them are travel and paperwork.
WORKLOAD = TimelineSpec(
    "showcase.workload", "Surveyor visits", claims.GRID, start="visit_from", end="inspected_at",
    lane="surveyor", label="{claim_number} · {insured}", tone="severity",
    href="/showcase/claims/{id}", lane_order="lane", height=560)

router = APIRouter()


def _claims(event: dict, zone: str, **params) -> str:
    """The Claims list narrowed to the event and zone (and a surveyor, or a view)."""
    narrow = {"x_event_code": event["code"], "x_zone": zone} | params
    return "/showcase/claims?" + urlencode(narrow)


def _graph(db: Db, event: dict) -> Graph:
    rows = db.all(SQL.deployment, event_id=event["id"])
    nodes = [GraphNode(f"event-{event['id']}", event["name"], event["code"], "danger",
                       f"/showcase/events/{event['id']}")]
    edges, seen = [], set()
    for r in rows:
        zone = str(r["zone_id"])                     # zone nodes are the Zones grid's rows
        if zone not in seen:
            seen.add(zone)
            total = sum(x["claims"] for x in rows if x["zone_id"] == r["zone_id"])
            waiting = sum(x["waiting"] for x in rows if x["zone_id"] == r["zone_id"])
            nodes.append(GraphNode(zone, r["zone"], f"Lead {r['lead']} · {total} claims, {waiting} waiting",
                                   "warning" if waiting else "success",
                                   _claims(event, r["zone"])))
            edges.append(GraphEdge(f"event-{event['id']}", zone))
        if r["claims"]:
            person = f"s-{r['zone_id']}-{r['surveyor_id'] or 'none'}"
            label = r["surveyor"] or "Not yet assigned"
            tone = "danger" if not r["surveyor"] else "info"
            href = (_claims(event, r["zone"], view="waiting") if not r["surveyor"]
                    else _claims(event, r["zone"], x_surveyor=r["surveyor"]))
            note = f"{r['claims']} claims" + (f", {r['priority']} priority" if r["priority"] else "")
            nodes.append(GraphNode(person, label, note, tone, href))
            edges.append(GraphEdge(zone, person, animated=not r["surveyor"]))
    return Graph(nodes=nodes, edges=edges, grid=ZONES, direction="LR", height=620)


@router.get("/deployment")
def deployment_page(request: Request, db: Db = Depends(get_db)):
    event = db.first(SQL.live_event)
    graph = build_graph(request, db, _graph(db, event)) if event else None
    workload = build_timeline(request, WORKLOAD, linked=False,
                              fixed={"event_code": event["code"]}) if event else None
    return render_page(request, "showcase/deployment.html", "claims.deployment", event=event,
                       graph=graph, workload=workload)
