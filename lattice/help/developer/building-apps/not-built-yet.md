---
title: Not built yet
summary: The graph component is planned but does not exist yet. What is planned, where it stands, and what to use meanwhile.
order: 110
keywords: graphs flows svelte flow xyflow dag stepper tree roadmap planned missing
---

Some components you might expect are **planned but not built**. They are not
in the code, the demo app has no example of them, and `lattice.api` does not
offer them. This page says what each will be, where it stands, and what to use
until then.

| Component | Status | Step of the plan |
|---|---|---|
| Graphs, flows and trees | Proposed; needs a trial first ([ADR 0005](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0005-graphs-xyflow-web-component.md)) | 5 |

It is being built now, in step 5, after [Charts](charts.md), [Record pages](record-pages.md) and [Forms from JSON Schema](json-forms.md). The full
order is in [Decisions and direction](../architecture/decisions.md).

## Graphs, flows and trees

**Planned:** three components, from simplest to richest:

| Component | Built with | For |
|---|---|---|
| **Stepper** | HTML and CSS only | Linear flows: the steps of a job, the stages of a process |
| **Tree** | HTML and CSS, collapsible | Hierarchies: a parent run and its child runs |
| **Graph** | Svelte Flow with automatic layout, packaged as a web component `<lt-graph>` | Networks and process maps where users click through to records and act from the graph |

**Before the graph is adopted,** a trial must show that it:

- works inside Lattice's pages;
- follows light and dark mode;
- lays out 200 nodes smoothly;
- can be used from the keyboard;
- has an acceptable file size.

If the trial fails, React Flow is the fallback.

**Until then:** for a linear history, use the `timeline` macro, which shows a
record's activity. For anything else there is no component.
