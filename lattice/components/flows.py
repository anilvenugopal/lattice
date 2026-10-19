"""Flows (ADR 0005): a stepper for linear flows, a tree for hierarchies, and a graph for DAGs.

    steps = [Step("Parse", "done", note="2.1 s"), Step("Extract", "current"), Step("Export")]
    {{ stepper(steps) }}

    {{ tree([TreeNode("Run 9f2", href="/jobs/runs/9f2", children=[TreeNode("Child run")])]) }}

    {{ graph(build_graph(request, db, Graph(nodes=[…], edges=[…], grid=RUNS_GRID))) }}

The stepper and tree are HTML and CSS. The graph is <lt-graph>, Svelte Flow with dagre
layout compiled into one web component (frontend/graph/, built into
static/js/vendor/graph/lt-graph.js). Its node actions are a grid's actions, run through the
grid's action endpoint, so "Retry" means the same in a grid and a graph.

Guide: lattice/help/developer/building-apps/flows.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fastapi import Request

from lattice.components.grid import engine
from lattice.components.grid.spec import GridSpec, Tone
from lattice.kernel.database import Db

StepState = Literal["done", "current", "failed", "waiting", "skipped"]
STATE_TONES: dict[str, Tone] = {"done": "success", "current": "info", "failed": "danger",
                                "waiting": "neutral", "skipped": "neutral"}


@dataclass
class Step:
    """One step of a linear flow."""

    label: str
    state: StepState = "waiting"
    note: str = ""                  # a second line: a duration, a time, an error
    href: str = ""                  # the label links here


@dataclass
class TreeNode:
    """One node of a tree. Nodes with children collapse."""

    label: str
    href: str = ""
    note: str = ""                  # muted text after the label
    badge: str = ""                 # a badge after the label…
    tone: Tone = "neutral"          # …in this tone
    children: list[TreeNode] = field(default_factory=list)
    open: bool = True               # shown expanded


@dataclass
class GraphNode:
    id: str                         # unique in the graph; a row id of `Graph.grid` for actions
    label: str
    note: str = ""                  # a second line
    tone: Tone = "neutral"          # border and badge colour, e.g. a status's tone
    href: str = ""                  # opened by double-click or Enter


@dataclass
class GraphEdge:
    source: str
    target: str
    label: str = ""
    animated: bool = False          # e.g. a step running now


@dataclass
class Graph:
    """A DAG or process map, laid out automatically (dagre)."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    direction: Literal["LR", "TB"] = "LR"   # left to right, or top to bottom
    height: int = 480               # pixels
    grid: GridSpec | None = None    # node ids are this grid's row ids; its actions run on nodes
    actions: list[str] = field(default_factory=list)  # which of the grid's actions; [] = all single/multi


def build_graph(request: Request, db: Db, graph: Graph) -> dict:
    """Context for the graph macro. Node actions are those the user may run that apply to the
    node's row, read through the grid's query: a node the grid would not show gets none."""
    user = request.state.user
    per_node: dict[str, list[str]] = {}
    actions: dict[str, dict] = {}
    if graph.grid is not None and user.can(graph.grid.permission):
        allowed = [a for a in graph.grid.actions_for(user)
                   if a.scope != "none" and a.handler and not a.fields
                   and (not graph.actions or a.key in graph.actions)]
        actions = {a.key: {"label": a.label, "confirm": a.confirm.replace("{count}", "1"),
                           "tone": a.tone} for a in allowed}
        rows = engine.fetch_by_ids(graph.grid, db, user, [n.id for n in graph.nodes])
        for row in rows:
            per_node[str(row["id"])] = [a.key for a in allowed if a.applies(row)]
    return {
        "height": graph.height,
        "spec": {
            "direction": graph.direction,
            "endpoint": f"/_grid/{graph.grid.key}" if graph.grid is not None else "",
            "actions": actions,
            "nodes": [{"id": n.id, "label": n.label, "note": n.note, "tone": n.tone,
                       "href": n.href, "actions": per_node.get(n.id, [])} for n in graph.nodes],
            "edges": [{"source": e.source, "target": e.target, "label": e.label,
                       "animated": e.animated} for e in graph.edges],
        },
    }
