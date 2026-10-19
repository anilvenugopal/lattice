# 0006. The taskline UI is a Lattice app, bundled or as an Ops console

Status: Accepted; partly superseded by [0012](0012-taskline-ui-and-contract.md) (name, reads, events, Ops console)

## Context

Taskline's requirements call for an admin UI:
- run list and run detail (FR-22);
- schedule management (FR-35);
- one view over several instances' databases (FR-44).

Its open question 2 asks whether the UI ships inside the taskline package.
Taskline imports nothing from its host, and must stay that way.

## Decision

- The UI is a separate package, `lattice-taskline`, a Lattice service app.
- It uses taskline's public Python API only: `taskline.queries` for reads, and
  taskline's commands for cancel, retry and schedules. It never reads the `jobs`
  tables directly.
- **Two modes, one package:**
  - **bundled** in a business host with one binding;
  - an **Ops console** host with one binding per taskline instance.
  - A host may do both.
- In the Ops console:
  - every id carries its instance (`prod/9f2…`);
  - grids have an Instance column and filter;
  - lists across instances use a merged grid source with keyset paging
    ([0008](0008-grid-data-sources.md));
  - permissions are scoped per instance (`taskline.operate@prod`).
- It contributes:
  - a Jobs record panel;
  - a `job_run` reference kind;
  - a Ctrl+J provider and home tiles;
  - the events `job.failed` and `job.succeeded`.

## Consequences

- Taskline stays free of web code and can change its schema without breaking the UI.
- The UI follows taskline's public API, so new screens may need new query methods in taskline.
- Hosts that include the app run Python 3.14, as taskline requires.

## Rejected

- **The UI inside the taskline package.** It would bring web dependencies into
  every taskline install.
- **Pages inside strategiq.** The Ops console could not reuse them.
- **Reading the `jobs` tables directly.** It would tie the UI to taskline's
  internal schema.
