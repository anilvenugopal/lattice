"""Maps (ADR 0013): points, hexagons, regions and areas from a grid's rows, behind its permission."""

from pathlib import Path

import pytest
from fastapi import APIRouter, Request

from lattice.api import (
    AppManifest,
    Areas,
    Column,
    Filter,
    GridSpec,
    Hexagons,
    MapSpec,
    Points,
    Regions,
    Sum,
    build_map,
)
from lattice.host import AppError, create_app
from lattice.kernel.services import audit
from lattice.kernel.sql import sql_queries

CHECK = sql_queries(Path(__file__).parent / "sql").checks
TONES = {"maptest.a": "danger", "maptest.b": "success"}
GRID = GridSpec(key="atlas.events", title="Events", path="/atlas", query=CHECK.mapped_events,
                columns=[Column("action", "Action", "badge", tones=TONES),
                         Column("county_fips", "County")],
                search=["action"], filters=[Filter("action", "Action", list(TONES.items()))],
                permission="lattice.audit.view")
CONE = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "Cone"},
        "geometry": {"type": "Point", "coordinates": [-95, 29]}}]}
MAP = MapSpec("atlas.map", "Events", GRID, layers=[
    Regions("county_fips", Sum("weight", "Weight"), map="us-counties"),
    Hexagons("h3_7"),
    Points("lon", "lat", color="action", label="#{id}", limit=2),
    Areas("cone", "Cone", load=lambda db, user, fixed: CONE)])
router = APIRouter()


@router.get("/page")
def page(request: Request):
    return build_map(request, MAP, fixed={"target_type": "t"})["config"]


@pytest.fixture
def host_apps():
    return [AppManifest(key="atlas", label="Atlas", routers=[router], grids=[GRID], maps=[MAP])]


@pytest.fixture
def events(db, users):
    for action, county in (("maptest.a", "1001"), ("maptest.a", "1001"), ("maptest.b", "48201")):
        audit.record(db, users["admin"].id, action, "x", "t", county)


def test_layers(as_user, events):
    data = as_user("admin").get("/_map/atlas.map/data").json()
    regions, hexes, points, areas = data["layers"]
    assert regions["kind"] == "regions" and regions["map"] == "us-counties"
    assert regions["values"] == {"01001": 2.0, "48201": 1.0}          # FIPS padded to 5
    assert hexes["values"] == {"87446124cffffff": 3.0}
    assert points["kind"] == "points" and len(points["rows"]) == 2 and points["truncated"]
    assert points["tones"] == TONES and points["rows"][0][3].startswith("#")
    assert areas["geojson"] == CONE and areas["tone"] == "danger"


def test_grid_filters_narrow_the_map(as_user, events):
    data = as_user("admin").get("/_map/atlas.map/data?f_action=maptest.b").json()
    assert data["layers"][0]["values"] == {"48201": 1.0}


def test_maps_need_the_grids_permission(as_user, events):
    assert as_user("editor").get("/_map/atlas.map/data").status_code == 403
    assert as_user("admin").get("/_map/nope/data").status_code == 404


def test_build_map_passes_fixed_filters_and_says_whether_a_basemap_exists(as_user, events):
    config = as_user("admin").get("/atlas/page?q=x&sort=id").json()
    assert config["params"] == "q=x&x_target_type=t" and config["grid"] == "atlas.events"
    assert config["basemap"] in ("", "/static/maps/basemap/us.pmtiles")


def test_a_missing_column_is_a_clear_error(as_user, events):
    from lattice.components.map import router as map_router
    map_router.register(MapSpec("atlas.bad", "Bad", GRID, layers=[Points("x", "y")]))
    res = as_user("admin").get("/_map/atlas.bad/data", headers={"Accept": "application/json"})
    assert res.status_code == 400 and "'x'" in res.json()["detail"]


@pytest.mark.parametrize("spec, message", [
    (MapSpec("other.m", "M", GRID, layers=[Hexagons("h3_7")]), "must start with 'atlas.'"),
    (MapSpec("atlas.m", "M", GRID), "has no layers"),
    (MapSpec("atlas.m", "M", GRID, layers=[Areas("a", "A", load=lambda d, u, f: {}),
                                            Areas("a", "B", load=lambda d, u, f: {})]), "share a key"),
])
def test_map_rules_stop_the_host(spec, message):
    with pytest.raises(AppError, match=message):
        create_app(apps=[AppManifest(key="atlas", label="Atlas", grids=[GRID], maps=[spec])])


def test_place_search_comes_from_the_maps_search_function(as_user, events):
    from lattice.components.map import router as map_router

    def find(db, user, text):
        return [{"label": f"{text} town", "lon": -95, "lat": 29.5, "kind": "place"}]
    map_router.register(MapSpec("atlas.searchable", "S", GRID, layers=[Hexagons("h3_7")], search=find))
    c = as_user("admin")
    assert c.get("/_map/atlas.searchable/places?q=Katy").json() == {
        "places": [{"label": "Katy town", "lon": -95.0, "lat": 29.5}]}
    assert c.get("/_map/atlas.map/places?q=Katy").status_code == 404        # no search function
    assert as_user("editor").get("/_map/atlas.searchable/places?q=Katy").status_code == 403
