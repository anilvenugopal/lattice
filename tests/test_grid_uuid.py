"""A grid whose query returns a uuid `id`, as Taskline's views do (Taskline UI's request L6)."""

from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, Request

from lattice.api import (
    Action,
    AppManifest,
    Column,
    Db,
    Graph,
    GraphNode,
    GridSpec,
    NavNode,
    build_graph,
    get_db,
    render_grid_page,
    sql_queries,
)
from lattice.components.grid import engine
from lattice.testing import current, post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks
ONE, TWO, THREE = (f"0199aaaa-0000-7000-8000-00000000000{n}" for n in (1, 2, 3))
SEEN: list = []


def touch(ctx):
    SEEN.extend(ctx.ids)
    return f"Touched {ctx.count}"


GRID = GridSpec(
    key="uuidapp.things", title="Things", path="/uuidapp/things", query=CHECK.uuid_things,
    columns=[Column("name", "Name", kind="strong"), Column("kind", "Kind"),
             Column("made_at", "Made", kind="datetime"), Column("id", "Id", kind="mono")],
    actions=[Action("touch", "Touch", handler=touch, when={"kind": ["a"]})],
    default_sort="-made_at",
)
router = APIRouter()


@router.get("/things")
def things(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "things")


@router.get("/graph")
def graph(request: Request, db: Db = Depends(get_db)):
    return build_graph(request, db, Graph(grid=GRID, nodes=[GraphNode(ONE, "one")], edges=[]))["spec"]


@pytest.fixture
def host_apps():
    return [AppManifest(key="uuidapp", label="UUID app", routers=[router], grids=[GRID],
                        nav=[NavNode("things", "Things", "/uuidapp/things")])]


def test_a_grid_page_renders_with_uuid_ids(as_user):
    page = as_user("admin").get("/uuidapp/things")
    assert page.status_code == 200 and ONE in page.text


def test_rows_are_found_by_id_as_the_browser_sends_it(db, users):
    rows = engine.fetch_by_ids(GRID, db, current(users["admin"]), [ONE, TWO])
    assert {str(r["id"]) for r in rows} == {ONE, TWO}


def test_an_id_that_is_not_a_uuid_is_dropped_not_an_error(db, users):
    assert engine.fetch_by_ids(GRID, db, current(users["admin"]), ["not-a-uuid"]) == []


def test_a_uuid_column_can_be_fixed(db, users):
    page = engine.fetch_page(GRID, db, current(users["admin"]), engine.GridQuery(fixed={"id": [THREE]}))
    assert [r["name"] for r in page.rows] == ["three"]


def test_an_action_receives_uuid_ids_and_is_audited(as_user):
    SEEN.clear()
    resp = post_json(as_user("admin"), "/_grid/uuidapp.things/action/touch", {"ids": [ONE, TWO]})
    assert resp.status_code == 200 and "1 skipped" in resp.json()["message"]   # two is kind b
    assert [str(i) for i in SEEN] == [ONE]


def test_a_graph_finds_its_nodes_rows(as_user):
    nodes = as_user("admin").get("/uuidapp/graph").json()["nodes"]
    assert nodes[0]["actions"] == ["touch"]
