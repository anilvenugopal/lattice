---
title: Flows
summary: Show the steps of a process with a stepper, a hierarchy with a tree, and a DAG with a graph whose nodes open records and run grid actions.
order: 26
keywords: flow stepper steps tree hierarchy graph dag network process map lineage svelte flow xyflow dagre lt-graph node action
---

Three components draw flows, from simplest to richest:

| Component | For | Built with |
|---|---|---|
| **Stepper** | Steps in order: a job's steps, the stages of a case | HTML and CSS |
| **Tree** | A hierarchy: a run and its child runs | HTML and CSS, collapsible |
| **Graph** | A DAG or process map: shared nodes, branches, joins; users open records and act from it | `<lt-graph>`: Svelte Flow with dagre layout |

All three are built in the route and placed with a macro:

```jinja
{% from "components/flows.html" import stepper, tree, graph %}
```

## Stepper

```python
from lattice.api import Step

steps = [Step("Received", "done", "Oct 12"),
         Step("Parse", "done", "2.1 s"),
         Step("Extract", "failed", "Timeout after 30 s", href="/jobs/tasks/81"),
         Step("Review"),
         Step("Export", "skipped")]
```

```jinja
{{ stepper(steps) }}                 {# left to right #}
{{ stepper(steps, vertical=true) }}  {# top to bottom, for a side column #}
```

| `Step` field | Use |
|---|---|
| `label` | The step's name |
| `state` | `done`, `current`, `failed`, `waiting` (default) or `skipped` |
| `note` | A second line: a duration, a time, an error |
| `href` | The label links here |

The current step carries `aria-current="step"`, and each step's state is read
out to screen readers.

## Tree

```python
from lattice.api import TreeNode

runs = [TreeNode("Run 9f2 · ingest", href="/jobs/runs/9f2", badge="Failed", tone="danger",
                 children=[TreeNode("Run a11 · parse", badge="Succeeded", tone="success",
                                    note="2.1 s")])]
```

```jinja
{{ tree(runs) }}
```

A node with children collapses and expands (`open=False` starts it
collapsed). `badge` and `tone` draw a badge; take them from a status `Column`
(`label_for`, `tone_for`) so they match the list.

## Graph

```python
from lattice.api import Graph, GraphEdge, GraphNode, build_graph

g = Graph(
    grid=WORK_GRID,             # node ids are this grid's row ids
    nodes=[GraphNode("1", "WI-00001 intake", "New", "info", "/demo/work/1"),
           GraphNode("2", "WI-00002 review", "In review", "warning", "/demo/work/2")],
    edges=[GraphEdge("1", "2", "next")],
    direction="LR")

return render_page(request, "demo/flow.html", "work.flow", g=build_graph(request, db, g))
```

```jinja
{% call card("Process", flush=True) %}{{ graph(g) }}{% endcall %}
```

The layout is automatic (dagre), left to right or top to bottom. Users pan by
dragging, zoom with the wheel or the controls, and see a minimap on graphs
over 30 nodes.

| Field | Use |
|---|---|
| `GraphNode(id, label, note, tone, href)` | `tone` colours the node's edge, e.g. its status's tone; `href` is opened by double-click, Enter, or **Open** |
| `GraphEdge(source, target, label, animated)` | `animated=True` for a step running now |
| `direction` | `LR` (default) or `TB` |
| `height` | Pixels; default 480 |
| `grid`, `actions` | Where node actions come from; see below |

### Node actions

Click a node, or Tab to it and press Space: a panel shows its label, **Open**,
and the actions that apply to it. They are the `grid`'s own actions, run
through the grid's action endpoint, so **Retry** on a graph node is exactly
**Retry** in the list: the same permission, `when` rule, confirm text and audit
event.

- **Which actions.** The grid's actions with a handler and no input fields,
  that the user may run (narrow them with `actions=["retry", "cancel"]`).
  Actions with input fields stay in the grid.
- **Per node.** `build_graph` reads the nodes' rows through the grid's query
  and keeps only actions whose `when` matches each row. A node whose id the
  grid would not show for this user gets no actions.
- **After an action** the page reloads and shows the result as a toast. A page
  that handles the browser event `lt-graph-action` itself (and calls
  `preventDefault()`) can refresh in place instead.

### How it is built

`<lt-graph>` is a web component: Svelte 5 and Svelte Flow (`@xyflow/svelte`)
with `@dagrejs/dagre`, compiled once from `frontend/graph/` into
`static/js/vendor/graph/lt-graph.js` (327 KB, 100 KB compressed) and
committed. Apps never run npm. It loads only on pages that place a graph, works
inside HTMX swaps, and takes its colours from the theme tokens, so it follows
light and dark mode.

To change the component itself: edit `frontend/graph/src/`, run `npm install`
and `npm run build` there, and commit the new `lt-graph.js`.
