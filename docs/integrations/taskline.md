# Taskline and Taskline UI

What Taskline UI needs from Taskline was agreed on 19 October 2026
([ADR 0012](../adr/0012-taskline-ui-and-contract.md)). The single source is now in the
Taskline repository (`anilvenugopal/taskline`, locally `~/projects/taskline`):

- `docs/public_contract.md`: every Python name, view, column, status value and
  refusal code Taskline UI may use, kept honest by a test;
- `docs/lattice_integration.md`: how Taskline, Taskline UI and Lattice fit
  together, and why.

The request Lattice first sent (`taskline-requirements.md`, 18 October 2026) is in
this repository's git history.

In short:

| | Taskline UI does | Through |
|---|---|---|
| Read | Lists of runs, tasks, references, events, queues, workers | The `taskline_api` views, with Lattice grids |
| Act | Cancel, retry, requeue, run a job | `taskline.api` async commands, from async grid actions, with an `actor` |
| React | Nothing yet. An app that must react to finished runs reads `taskline_api.run` on a timer | No events |
