---
title: Decisions and direction
summary: Where Lattice is going, the order of the work, and the decision records behind it.
order: 10
keywords: roadmap adr decision record target design postgres permissions references events
---

Lattice is part-way to its target design. This page summarises the target, the
order of the work and the recorded decisions. The full design is in
[ARCHITECTURE.md](https://github.com/anilvenugopal/lattice/blob/main/docs/ARCHITECTURE.md),
and each decision has its own record in
[docs/adr](https://github.com/anilvenugopal/lattice/tree/main/docs/adr).

## The target

Lattice hosts two kinds of app, built the same way:

- **Business apps** serve one business domain, such as underwriting or a risk
  workbench.
- **Service apps** offer something every other app can use: Jobs (taskline),
  Incidents, Notifications.

They cooperate through kernel contracts and never import each other:

| Contract | What it gives |
|---|---|
| **References** | A typed pointer to any record, `kind:id`, which any page can show as a link with a preview |
| **Record panels** | Sections that one app adds to another app's record pages, such as a Jobs panel on a document |
| **Events** | An in-process bus: `job.failed` can open an incident |
| **Permissions** | Declared by apps, grouped into roles by administrators, optionally scoped to one database binding |

More components join the grid: forms rendered from JSON Schema, charts
(Chart.js), and a stepper, tree and graph for flows.

## Where it stands

| Area | Today | Target |
|---|---|---|
| Apps | `AppManifest` and `create_app` with namespace checks | Also settings, bindings, permissions, references, panels and events in the manifest |
| Database | SQLite, one connection, one Alembic history | Postgres; each app its own schema, migrations and binding |
| Access | Roles (`admin`, `editor`, `viewer`) | Permissions grouped into roles |
| Grid | A SQLAlchemy query with offset paging | Data sources, keyset paging, async sources |
| Between apps | Nothing needed yet | References, record panels, events |
| Components | Grid, Ctrl+J, help, tiles, macros, timeline | Also forms, charts, stepper, tree, graph, record view |

## Order of the work

Each step ends with every test passing and the demo running. Each is reviewed
before the next starts.

1. **Kernel restructure.** Done: the `lattice` package with its layers,
   `lattice.api`, `AppManifest`, the demo as its own app, theming rules, the
   `lattice` command.
2. **Postgres and bindings**: per-app schemas and migrations; SQLite removed.
   Trigram indexes for grid search, a time limit on grid queries, and the
   query plans of the demo grids checked on Postgres.
3. **Permissions** replace role checks.
4. **References, record panels and events**, and the record view.
5. **Grid data sources** with keyset paging, an optional estimated count for
   large lists, and streaming CSV export.
6. **Taskline app** spike: runs, run detail, queues, cancel and retry.
7. **Charts.**
8. **Graph** component spike.
9. **JSON Schema forms** and the document store.
10. **Incidents app.**

> [!IMPORTANT]
> Steps 2 and 3 change how apps declare tables and access. Write apps against
> today's rules (one migration history, `roles=`); the change will come with a
> migration guide.

## Decision records

| # | Decision | Status |
|---|---|---|
| 0001 | Postgres only, with per-app database bindings | Accepted |
| 0002 | One core package with enforced boundaries; each app its own package | Accepted |
| 0003 | Apps plug in through a manifest and kernel contracts | Accepted |
| 0004 | Charts with Chart.js and its plugins | Accepted |
| 0005 | Graphs with Svelte Flow compiled to a web component | Proposed, needs a spike |
| 0006 | The taskline UI is a Lattice app, bundled or as an Ops console | Accepted |
| 0007 | Forms rendered from JSON Schema, JSON in and JSON out | Proposed |
| 0008 | Grid rows come from data sources with keyset paging | Proposed |
| 0009 | Permissions declared by apps, grouped into roles | Proposed |
| 0010 | Theming and overrides: the host owns the brand, apps style only their own pages | Proposed |

A record is never rewritten once accepted. A later decision that changes it is
a new record naming the one it replaces.
