"""Locations: the exposure snapshot, searched by drawing on the map.

Draw a polygon, rectangle or circle and the list, totals and charts narrow to the locations
inside. **Save as area** keeps the shape (an evacuation zone, a flood basin) as a named
area, which can become an event's footprint.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Request

import geoengine
from lattice.api import (
    Action,
    ActionContext,
    ActionResult,
    ChartSpec,
    Db,
    Field,
    Filter,
    GridSpec,
    Hexagons,
    Highlight,
    MapSpec,
    Points,
    Sum,
    build_chart,
    build_grid,
    build_map,
    get_db,
    render_page,
    sql_queries,
)
from lattice_showcase import events, places
from lattice_showcase.exposure import CONSTRUCTION, LINES, TIERS, location_columns

QUERIES = sql_queries(Path(__file__).parent / "sql")


def save_area(ctx: ActionContext) -> ActionResult:
    shape = ctx.query.shape if ctx.query else ""
    if not shape:
        return ActionResult("Draw a shape on the map first.", tone="warning", refresh=False)
    name = ctx.values["name"].strip()
    if ctx.db.first(QUERIES.events.area_by_name, name=name):
        return ActionResult(f"An area named {name!r} already exists.", tone="warning", refresh=False)
    key = "area-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    layer = geoengine.create_layer(ctx.db.conn, key, "areas", name)
    geoengine.put_geojson(ctx.db.conn, layer, {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": "area", "properties": {"name": name}, "geometry": json.loads(shape)}]})
    ctx.db.value(QUERIES.events.add_area, name=name, layer=key, created_by=ctx.user.id)
    return ActionResult(f"Saved area {name!r}. Use it as a footprint when you declare an event.",
                        refresh=False)


GRID = GridSpec(
    key="showcase.locations", title="Locations", path="/showcase/locations",
    query=QUERIES.locations.grid, columns=location_columns(), spatial=("lon", "lat"),
    search=["ref", "insured", "policy_number", "city", "county"],
    filters=[Filter("line", "Line", LINES), Filter("construction", "Construction", CONSTRUCTION),
             Filter("quality", "Location quality", TIERS),
             Filter("state", "State", [("TX", "Texas"), ("LA", "Louisiana"), ("FL", "Florida"),
                                       ("CA", "California")])],
    actions=[Action("save_area", "Save as area", scope="none", handler=save_area, icon="bookmark",
                    permission=events.MANAGE,
                    fields=[Field("name", "Area name", required=True,
                                  placeholder="Evacuation zone 3")])],
    default_sort="-tiv",
)
MAP = MapSpec("showcase.locations_map", "Insured value", GRID, format="money", height=540, search=places.find,
              layers=[
    Hexagons("h3_7", Sum("tiv", "Insured value"), title="Concentration"),
    Points("lon", "lat", color="quality", label="{ref}", title="Locations", limit=50_000),
])
CHARTS = [
    ChartSpec("showcase.locations_by_line", "Insured value by line and construction", GRID,
              "treemap", x="construction", series="line", y=Sum("tiv", "Insured value"),
              format="money", height=260),
    ChartSpec("showcase.locations_by_state", "Insured value by state", GRID, "bar", x="state",
              y=Sum("tiv", "Insured value"), format="money", height=260),
    ChartSpec("showcase.locations_quality", "Location quality", GRID, "doughnut", x="quality",
              height=260, highlight=[Highlight(values=["zip", "county"], tone="warning")]),
]

router = APIRouter()


@router.get("/locations")
def locations_page(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "showcase/locations.html", "locations",
                       grid=build_grid(request, db, GRID), map=build_map(request, MAP),
                       charts=[build_chart(request, c) for c in CHARTS])
