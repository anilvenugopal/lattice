"""A grid's spatial filter: rows narrowed to a shape drawn on a map (ADR 0013)."""

import json
from pathlib import Path

import pytest

import geoengine
from lattice.api import AppManifest, Column, GridSpec
from lattice.components.grid import engine, views
from lattice.kernel.services import audit
from lattice.kernel.sql import sql_queries
from lattice.testing import current

CHECK = sql_queries(Path(__file__).parent / "sql").checks
GRID = GridSpec(key="atlas.events", title="Events", path="/atlas", query=CHECK.mapped_events,
                columns=[Column("action", "Action")], spatial=("lon", "lat"))
# Events with ids 1–3 sit at lon -94.99, -94.98, -94.97 (see checks.mapped_events).
BOX = {"type": "Polygon", "coordinates": [[[-94.995, 29], [-94.975, 29], [-94.975, 30],
                                           [-94.995, 30], [-94.995, 29]]]}


@pytest.fixture
def host_apps():
    # The schema brings PostGIS into the test database.
    return [AppManifest(key="atlas", label="Atlas", grids=[GRID],
                        library_schemas=[geoengine.SCHEMA])]


@pytest.fixture
def events(db, users):
    for _ in range(3):
        audit.record(db, users["admin"].id, "maptest.x", "x", "t", "1")


def test_a_shape_narrows_rows_counts_and_exports(db, users, events):
    me = current(users["admin"])
    assert engine.count(GRID, db, me, engine.GridQuery()) == 3
    inside = engine.fetch_page(GRID, db, me, engine.GridQuery(shape=json.dumps(BOX)))
    assert inside.total == 2


def test_the_shape_travels_in_the_url(as_user, events):
    c = as_user("admin")
    html = c.get("/_grid/atlas.events/rows", params={"shape": json.dumps(BOX)}).text
    assert html.count("<tr data-id") == 2


@pytest.mark.parametrize("bad", ["not json", json.dumps({"type": "Point", "coordinates": [0, 0]}),
                                 json.dumps({"type": "Polygon", "coordinates": [[[0, 0]] * 2001]})])
def test_bad_shapes_are_refused(as_user, events, bad):
    c = as_user("admin")
    assert c.get("/_grid/atlas.events/rows", params={"shape": bad}).status_code == 400


def test_grids_without_spatial_ignore_shapes():
    plain = GridSpec(key="atlas.plain", title="P", path="/atlas", query=CHECK.mapped_events,
                     columns=[Column("action", "A")])
    from starlette.datastructures import QueryParams
    assert engine.GridQuery.from_params(QueryParams({"shape": "x"}), plain).shape == ""


def test_saved_views_keep_the_shape():
    state = views.clean_state(GRID, "shape=" + json.dumps(BOX) + "&page=2")
    assert "shape=" in state and "page" not in state
