# 0005. Graphs with Svelte Flow compiled to a web component

Status: Accepted (18 October 2026). The spike below passed in step 5.

## Context

Process flows, job lineage and dependency DAGs must let users navigate (open the
record behind a node) and act (retry, cancel) from the graph. The requested
libraries are React Flow and Svelte Flow (both xyflow, MIT). Lattice is
server-rendered with htmx and Alpine and has no frontend build.

## Decision

- Three components:
  - **stepper** (HTML and CSS) for linear flows;
  - **tree** (HTML and CSS) for hierarchies;
  - **graph** for DAGs and process maps.
- The graph is Svelte Flow with dagre layout, compiled into a web component,
  `<lt-graph spec='…'>`. It is built in `frontend/graph/` with Vite, and the
  output file is committed to `static/`. App authors never run npm.
- Nodes carry references: a click opens the preview or the record through the
  reference registry.
- Node actions use the grid's action model and endpoint, so an action means the
  same thing in a grid and in a graph.
- The rule "no npm build" becomes "no npm build except committed component builds".

## Spike (must pass before adoption)

- The component works inside htmx swaps and Alpine pages.
- It takes its colours from the CSS tokens in light and dark mode.
- It lays out and renders a 200-node DAG smoothly.
- Nodes can be reached and opened with the keyboard.
- Size of the built file: recorded and accepted.

## Spike result (18 October 2026)

Built with Svelte 5.57.1, @xyflow/svelte 1.7.0 and @dagrejs/dagre 3.1.1 (Vite 8.3.2):

| Criterion | Result |
|---|---|
| htmx swaps and Alpine pages | Passed: a graph swapped in by `htmx.ajax` upgrades and renders |
| Colours from the tokens, light and dark | Passed: the tokens reach into the shadow root; Svelte Flow's own variables are mapped to them |
| A 200-node DAG | Passed: laid out and drawn in about half a second |
| Keyboard | Passed: Tab reaches nodes; selecting one shows its actions; Enter opens its record |
| Size | 327 KB, 100 KB compressed; loaded only on pages with a graph. Accepted |

## Consequences

- One build toolchain to maintain, confined to `frontend/graph/`.
- Taskline v1 chains are sequential, so the stepper and the tree cover its first
  pages. The graph is needed for lineage with shared nodes and for process maps.

## Rejected or fallback

- **React Flow.** It works the same way as a web component but ships React and
  ReactDOM, roughly three times the size. It is the fallback if the Svelte Flow
  spike fails.
- **Cytoscape.js.** It does not give the node-as-component model that navigation
  and actions need.
- **Mermaid.** It is for read-only diagrams.
