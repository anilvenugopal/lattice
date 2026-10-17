# 0003. Apps plug in through a manifest and kernel contracts

Status: Accepted

## Context

Business apps and service apps (taskline, incidents, notifications) must work
together without importing each other. For example, a strategiq document page
should show its taskline runs and incidents, and a failed job should open an
incident.

## Decision

- Each app exposes one `AppManifest`. It declares:
  - nav nodes and routers;
  - grids, search providers and home tiles;
  - permissions;
  - reference kinds and record panels;
  - published and subscribed events;
  - bindings, migrations and settings;
  - an optional background task.
- `create_app(apps=[...])` registers each manifest with the kernel. Each app gets:
  - the URL prefix `/{key}`;
  - templates under `{key}/`;
  - static files at `/static/{key}/`;
  - settings under `LATTICE_{KEY}_`.
- The kernel contracts are:
  - **references:** `kind:id` with a resolver for title, URL and preview;
  - **record panels:** sections an app adds to other apps' record pages,
    matched on reference kind;
  - **events:** an in-process bus; publish after commit; names `{app}.{event}`;
    small payloads;
  - **registries:** for nav, search, grids, tiles and permissions.
- An app's CSS declares `@layer components { … }`.

## Consequences

- A business app gets the Jobs and Incidents panels by using the record view, with
  no code for each service app.
- Events are not delivered after a crash between commit and subscriber. An app
  that needs that adds an outbox.
- The manifest is the list of what an app adds to a host, which helps review and
  documentation.

## Rejected

- **Python entry-point discovery as the only mechanism.** Hosts list their apps
  explicitly so the set and order are visible; entry points can be added for
  tooling later.
- **A message broker for events.** Not needed while apps run in one process.
