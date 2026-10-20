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
| **Events** | Something happened: `comments.added` tells the record's owner. An in-process bus within a host; HTTP from remote systems later | CloudEvents 1.0 |
| **Published views** | Reading another system's data in a database the host can read, such as Taskline's runs | Read-only SQL views, as that system's contract |
| **Calls between processes** | One process asking another to act | HTTP and JSON, described with OpenAPI 3.1 |
| **Permissions** | Declared by apps, grouped into roles by administrators, optionally scoped to one database binding | — |

More components join the grid: charts (Chart.js), forms rendered from JSON
Schema, a stepper, tree and graph for flows, a record page component and saved
grid views.

**Ecosystem apps have their own repositories.** Taskline (the job engine, which
never depends on Lattice), Taskline UI (`taskline-ui`, a Lattice app that reads
Taskline's views and calls its commands) and Incidents each live apart from
Lattice. Taskline UI and Incidents depend on Lattice by git tag. This repository keeps the core and the showcase.

## Where it stands

| Area | Today | Target |
|---|---|---|
| Apps | `AppManifest` and `create_app` with namespace checks | Also settings, bindings, permissions, references, panels and events in the manifest |
| Database | Postgres 18; one database, a schema and SQL migrations per app; plain SQL, no ORM | Unchanged; separate databases per app only when one needs it |
| Access | Permissions declared by apps, grouped into roles administrators edit | + scopes per database binding |
| Grid | A named SQL query, offset paging, a time limit | Data sources, keyset paging, async sources |
| Between apps | Nothing needed yet | URN references, record panels, CloudEvents, published views |
| Components | Grid with saved views, charts, record page, JSON Schema forms, document store, stepper, tree, graph; Ctrl+J, help, tiles, macros, timeline | Panels from other apps on the record page |

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
5. **Core components.** Done: saved grid views, charts, the record page
   component, forms from JSON Schema with the document store, and flows
   (stepper, tree and graph).
6. **The showcase.** Done: one app, one page per capability on sample data,
   replaces the demo.
7. **Integration framework.** Done: URN references, record panels and the
   CloudEvents bus.
8. **The showcase uses the framework.** Done: the Comments app comments on any
   record; the showcase tells a claim's handler about new comments.
9. **Taskline UI:** Taskline builds its public contract (views and async
   commands, release 0.2.0); Lattice adds async grid actions and moves to
   Postgres 18; then Taskline UI in its own repository.
10. **Catastrophe response showcase.** Done: the sample pages give way to a
    carrier responding to catastrophes; geoengine and the map component
    (ADR 0013).
11. **Incidents** in its own repository.

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
| 0005 | Graphs with Svelte Flow compiled to a web component | Accepted |
| 0006 | The taskline UI is a Lattice app, bundled or as an Ops console | Accepted; partly superseded by 0012 |
| 0007 | Forms rendered from JSON Schema, JSON in and JSON out | Accepted |
| 0008 | Grid rows come from data sources with keyset paging | Accepted in part (keyset paging) |
| 0009 | Permissions declared by apps, grouped into roles | Accepted |
| 0010 | Theming and overrides: the host owns the brand, apps style only their own pages | Proposed |
| 0011 | Integration standards: URN references, CloudEvents, published views, OpenAPI between processes | Accepted |
| 0012 | Taskline UI on Taskline's published contract: views, async commands, no events | Accepted |
| 0013 | Geospatial: a separate geoengine package, PostGIS, and a Lattice map component | Accepted |
| 0014 | Timelines: a TimelineSpec component drawn in HTML | Accepted |
| 0015 | Chart colours: one hue by default, colour only where it means something | Accepted |

A record is never rewritten once accepted. A later decision that changes it is
a new record naming the one it replaces.
