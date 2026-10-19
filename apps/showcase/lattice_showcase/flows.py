"""Flows: a stepper, a tree of items and their children, and a graph of item dependencies
whose node actions are the Items grid's actions."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from lattice.api import (
    Db,
    Graph,
    GraphEdge,
    GraphNode,
    Step,
    TreeNode,
    build_graph,
    get_db,
    render_page,
    sql_queries,
)
from lattice_showcase.items import GRID, STATUS_TONES, STATUSES

SQL = sql_queries(Path(__file__).parent / "sql").items
router = APIRouter()

PIPELINE = [Step("Received", "done", "Oct 12, 09:14"), Step("Validated", "done", "0.4 s"),
            Step("Enriched", "done", "2.1 s"), Step("Reviewed", "current", "Waiting for Sam"),
            Step("Published"), Step("Archived", "skipped")]


def _tree(db: Db) -> list[TreeNode]:
    labels = dict(STATUSES)
    roots = db.all(SQL.roots, limit=6)
    kids = db.all(SQL.children, ids=[r["id"] for r in roots]) if roots else []
    grandkids = db.all(SQL.children, ids=[k["id"] for k in kids]) if kids else []

    def node(r, below, is_open=False):
        return TreeNode(f"{r['ref']} · {r['name']}", href=f"/showcase/items/{r['id']}",
                        badge=labels[r["status"]], tone=STATUS_TONES[r["status"]], open=is_open,
                        children=[node(c, []) for c in below if c["parent_id"] == r["id"]])

    return [TreeNode(f"{r['ref']} · {r['name']}", href=f"/showcase/items/{r['id']}",
                     badge=labels[r["status"]], tone=STATUS_TONES[r["status"]], open=i == 0,
                     children=[node(k, grandkids) for k in kids if k["parent_id"] == r["id"]])
            for i, r in enumerate(roots)]


def _graph(db: Db) -> Graph:
    labels = dict(STATUSES)
    nodes = [GraphNode(str(r["id"]), f"{r['ref']} · {r['name']}", labels[r["status"]],
                       STATUS_TONES[r["status"]], f"/showcase/items/{r['id']}")
             for r in db.all(SQL.linked)]
    edges = [GraphEdge(str(e["from_id"]), str(e["to_id"])) for e in db.all(SQL.links)]
    return Graph(nodes=nodes, edges=edges, grid=GRID, actions=["complete", "star", "delete"],
                 height=560)


@router.get("/flows")
def flows_page(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "showcase/flows.html", "flows", steps=PIPELINE,
                       tree_nodes=_tree(db), graph_ctx=build_graph(request, db, _graph(db)))
