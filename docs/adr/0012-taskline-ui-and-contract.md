# 0012. Taskline UI on Taskline's published contract: views, async commands, no events

Status: Accepted (19 October 2026). Supersedes the parts of
[0006](0006-taskline-as-lattice-app.md) named below, and the outbox row of
[0011](0011-integration-standards.md)'s event delivery; the rest of both stands.

## Context

[ADR 0006](0006-taskline-as-lattice-app.md) made Taskline's admin UI a Lattice app
named `lattice-taskline`, reading through `taskline.queries` and contributing the
events `job.failed` and `job.succeeded`. Lattice then asked Taskline for what the UI
needs (`docs/integrations/taskline-requirements.md`, 18 October 2026, now in git
history; see `docs/integrations/taskline.md`). Taskline
reviewed it and proposed a lighter contract, which the owner approved on
19 October 2026. Its written form is Taskline's `docs/public_contract.md`.

## Decision

**Three packages, each in its own repository:**

| Package | What it is | Depends on |
|---|---|---|
| **Taskline** (`taskline`) | The job engine | Nothing of Lattice or Taskline UI |
| **Taskline UI** (`taskline-ui`, package `taskline_ui`, app key `taskline`) | The admin screens, a Lattice app | Lattice (`lattice.api`) and Taskline's public contract |
| **Lattice** (`lattice`) | The platform | Nothing of Taskline |

A host lists `taskline_ui.APP` among its apps; Lattice never names Taskline.

**Reading.** Taskline UI reads only the `taskline_api` views (`run`, `task`,
`reference`, `event`, `queue`, `worker`, `instance`, later `schedule`), with
Lattice's ordinary grids and named queries. Not `taskline.queries`, and never the
`jobs` tables.

**Acting.** Taskline UI calls Taskline's async command functions in `taskline.api`
(`cancel_run`, `retry_run`, `requeue`, `submit_job`), passing an `actor` such as
`lattice:user:42` and a registered producer. They use Taskline's own connection,
from its `TASKLINE_*` settings, and commit in their own transaction: Lattice's audit
record follows in the request's transaction. Lattice grid actions may be `async` for
this.

**No events.** Taskline publishes no event feed. An app that must react to finished
runs (Incidents, later) reads `taskline_api.run` on a timer for runs in a time
window and remembers which it has handled. Lattice's own event feed reader is
removed: reading "everything after the last id" can miss rows that become visible
out of order.

**References.** Taskline UI builds URNs in its own queries from a reference's kind
and external id; Taskline adds no `urn` column.

**Versions.** Taskline UI pins Taskline's package version (`taskline>=0.2,<0.3`
first). One version number: the package's.

**Postgres 18.** Taskline's schema uses `uuidv7()`, so a database holding
Taskline's tables runs Postgres 18 or later. Lattice moves to Postgres 18.

## What changes in 0006

| 0006 said | Now |
|---|---|
| Package `lattice-taskline` | Taskline UI, `taskline-ui` |
| Reads through `taskline.queries` | Reads the `taskline_api` views |
| Contributes events `job.failed`, `job.succeeded` | No events |
| Ops console over several instances, merged grid source, per-instance permissions | Deferred: Taskline's commands serve one instance per process. Revisit when an Ops console is needed |

Still as in 0006: the UI is a separate Lattice app, not part of the Taskline
package; it may contribute a Jobs record panel, Ctrl+J and home tiles.

## Consequences

- The UI needs no new Lattice machinery to read: grids over views work today.
- Lattice adds async action handlers; it needs no async engine of its own.
- The bounded loss: if a request fails after a Taskline command committed, the
  run changed without a Lattice audit row. Taskline's event log records the actor.
- ADR 0008 (grid data sources, keyset paging) is not needed for Taskline UI with
  one instance. It stays Proposed for the Ops console.

## Rejected

- **A CloudEvents feed from Taskline.** A cursor over a sequence can skip rows;
  nothing needs events yet.
- **Sharing Lattice's connection pool with Taskline.** Lattice's pool is sync,
  Taskline's async.
- **A REST service around Taskline now.** Taskline UI runs in-process; HTTP would
  add tokens and failure modes for nothing.
