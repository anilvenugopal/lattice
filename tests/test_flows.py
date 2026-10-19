"""Flows: stepper and tree macros, and the graph's node actions from a grid."""

import json
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, Request

from lattice.api import (
    AppManifest,
    Db,
    Graph,
    GraphEdge,
    GraphNode,
    Step,
    TreeNode,
    build_graph,
    get_db,
    render,
)
from lattice.platform.admin import USERS

router = APIRouter()
GRAPH = {}


@router.get("/flows")
def flows(request: Request, db: Db = Depends(get_db)):
    return render(request, "people/flows.html",
                  steps=[Step("Parse", "done", "2 s"), Step("Extract", "failed", href="/x"),
                         Step("Export")],
                  nodes=[TreeNode("Run 1", badge="Failed", tone="danger",
                                  children=[TreeNode("Run 2", href="/runs/2")])],
                  g=build_graph(request, db, GRAPH["g"]))


@pytest.fixture
def host_apps():
    return [AppManifest(key="people", label="People", routers=[router],
                        templates=Path(__file__).parent / "templates")]


def spec_of(html: str) -> dict:
    import html as h
    raw = html.split('spec="', 1)[1].split('"', 1)[0]
    return json.loads(h.unescape(raw))


def test_stepper_and_tree(as_user, users):
    GRAPH["g"] = Graph(nodes=[], edges=[])
    html = as_user("viewer").get("/people/flows").text
    assert 'class="stepper__step is-done"' in html and 'aria-current' not in html
    assert 'is-failed' in html and 'href="/x"' in html
    assert '<details class="tree__branch" open' in html and 'href="/runs/2"' in html


def test_node_actions_come_from_the_grid_and_its_rows(as_user, users):
    active, inactive = users["viewer"].id, users["editor"].id
    c = as_user("admin")
    c.post("/_grid/users/action/deactivate", json={"ids": [inactive]},
           headers={"X-CSRF-Token": c.cookies["lattice_csrf"]})
    GRAPH["g"] = Graph(grid=USERS, nodes=[GraphNode(str(active), "Viewer"),
                                          GraphNode(str(inactive), "Editor"),
                                          GraphNode("999999", "Gone")],
                       edges=[GraphEdge(str(active), str(inactive))])
    spec = spec_of(c.get("/people/flows").text)
    by_id = {n["id"]: n["actions"] for n in spec["nodes"]}
    assert "deactivate" in by_id[str(active)] and "activate" not in by_id[str(active)]
    assert "activate" in by_id[str(inactive)]
    assert by_id["999999"] == []                       # not a row of the grid: no actions
    assert "grant" not in spec["actions"]               # needs input fields: grids only
    assert spec["endpoint"] == "/_grid/users"


def test_no_actions_without_the_grids_permission(as_user, users):
    GRAPH["g"] = Graph(grid=USERS, nodes=[GraphNode(str(users["viewer"].id), "Viewer")], edges=[])
    spec = spec_of(as_user("editor").get("/people/flows").text)
    assert spec["actions"] == {} and spec["nodes"][0]["actions"] == []
