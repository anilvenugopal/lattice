---
title: Decisions and direction
summary: Where Lattice is going, the order of the work, and the decision records behind it.
order: 10
keywords: roadmap adr decision record target design postgres permissions references events urn cloudevents openapi repositories
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

They cooperate through kernel contracts and never import each other. Where a
standard exists, the contract follows it
([ADR 0011](https://github.com/anilvenugopal/lattice/blob/main/docs/adr/0011-integration-standards.md)):

| Contract | What it gives | Standard |
|---|---|---|
| **References** | A pointer to any record, which any page can show as a link: `urn:lattice:demo.work_item:42` | URN (RFC 8141) |
| **Record panels** | Sections that one app adds to another app's record pages, such as a Jobs panel on a document | A small Lattice registry; no standard fits |
| **Events** | Something happened: `taskline.run.failed` can open an incident. The in-process bus within a host, an outbox from other processes, HTTP from remote systems | CloudEvents 1.0 |
| **Published views** | Reading another system's data in a database the host can read, such as Taskline's runs | Read-only SQL views, as that system's contract |
| **Calls between processes** | One process asking another to act | HTTP and JSON, described with OpenAPI 3.1 |
| **Permissions** | Declared by apps, grouped into roles by administrators, optionally scoped to one database binding | — |

More components join the grid: charts (Chart.js), forms rendered from JSON
Schema, a stepper, tree and graph for flows, a record page component and saved
grid views.

**Ecosystem apps have their own repositories.** Taskline (the job engine, which
never depends on Lattice), the Taskline UI (`lattice-taskline`, which also runs
as an Ops console) and Incidents each live apart from Lattice and depend on it
by git tag. This repository keeps the core and the showcase apps.

## Where it stands

| Area | Today | Target |
|---|---|---|
| Apps | `AppManifest` and `create_app` with namespace checks | Also settings, bindings, permissions, references, panels and events in the manifest |
| Database | Postgres 17; one database, a schema and SQL migrations per app; plain SQL, no ORM | Unchanged; separate databases per app only when one needs it |
| Access | Permissions declared by apps, grouped into roles administrators edit | + scopes per database binding |
| Grid | A named SQL query, offset paging, a time limit | Data sources, keyset paging, async sources |
| Between apps | Nothing needed yet | URN references, record panels, CloudEvents, published views |
| Components | Grid, Ctrl+J, help, tiles, macros, timeline | Also charts, forms, stepper, tree, graph, record page, saved views |

## Order of the work

Each step ends with every test passing and the demo running. Each is reviewed
before the next starts.

1. **Kernel restructure.** Done: the `lattice` package with its layers,
   `lattice.api`, `AppManifest`, the demo as its own app, theming rules, the
   `lattice` command.
2. **Postgres and plain SQL.** Done: Postgres only, a schema and SQL migrations
   per app, named SQL queries with no ORM, one transaction per request, a time
   limit on grid queries, and the grids' query plans checked on Postgres.
3. **Permissions** replace role checks. Done: apps declare permissions, roles
   are sets of them, every check names a permission.
4. **Integration standards.** Done: ADR 0011, this order of work, and what
   Taskline must provide.
5. **Core components:** charts, forms from JSON Schema with the document store,
   flows (stepper, tree, then the graph trial), the record page component and
   saved grid views.
6. **Showcase apps** replace the demo, built to show Lattice's capabilities.
7. **Integration framework:** URN references, record panels, the CloudEvents
   bus and its outbox reader.
8. **The showcase apps use the framework.**
9. **Taskline in the ecosystem:** Taskline in its own repository with its
   public contract; in Lattice, an async engine, grid data sources and database
   bindings; then the `lattice-taskline` app and Ops console.
10. **Incidents** in its own repository.

## Database decisions (step 2)

Taken while planning step 2, on 18 October 2026:

| Decision | Instead of |
|---|---|
| Plain SQL in named `.sql` files; no ORM | SQLAlchemy ORM model classes |
| SQLAlchemy Core with the psycopg 3 driver; one shared engine | psycopg alone; an engine per app |
| One database, a schema per app; apps may join Lattice's user table | A database per app (ADR 0001's bindings), built only when an app needs one |
| Plain `.sql` migrations and a small runner, like taskline | Alembic |
| One transaction per request | Routes committing themselves |
| Sync database access; async is added with Taskline in step 9 | Async now |
| Grid search keeps joined columns; trigram indexes only where a large table needs search | Searching own columns only |

## Decision records

| # | Decision | Status |
|---|---|---|
| 0001 | Postgres only, with per-app database bindings | Accepted |
| 0002 | One core package with enforced boundaries; each app its own package | Accepted |
| 0003 | Apps plug in through a manifest and kernel contracts | Accepted |
| 0004 | Charts with Chart.js and its plugins | Accepted |
| 0005 | Graphs with Svelte Flow compiled to a web component | Proposed, needs a spike |
| 0006 | The taskline UI is a Lattice app, bundled or as an Ops console | Accepted |
| 0007 | Forms rendered from JSON Schema, JSON in and JSON out | Accepted |
| 0008 | Grid rows come from data sources with keyset paging | Proposed |
| 0009 | Permissions declared by apps, grouped into roles | Accepted |
| 0010 | Theming and overrides: the host owns the brand, apps style only their own pages | Proposed |
| 0011 | Integration standards: URN references, CloudEvents, published views, OpenAPI between processes | Accepted |

A record is never rewritten once accepted. A later decision that changes it is
a new record naming the one it replaces.
