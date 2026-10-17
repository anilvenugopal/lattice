# 0002. One core package with enforced boundaries; each app its own package

Status: Proposed. Condition from review: clear documentation and code
organisation are required.

## Context

Lattice has a kernel (auth, permissions, navigation, data access) and UI
components (grid, form, chart, graph). Apps must install into different hosts:
taskline's UI goes into strategiq's host and into an Ops console. The question is
whether the kernel and the components should also be separate packages.

## Decision

- One core package, `lattice`, with `lattice/kernel/` and `lattice/components/`.
- Every app is its own package from the start: `lattice-taskline`,
  `lattice-incidents`, the demo app, and each business app.
- Apps import only `lattice.api`. Removing or changing a name there is a breaking
  change.
- Import contracts are checked by a test (`import-linter`):
  - components may import the kernel, never the reverse;
  - apps import only `lattice.api`;
  - apps never import each other.
- Documentation:
  - `docs/ARCHITECTURE.md`;
  - one page per component;
  - an app-author guide;
  - these records.

## Consequences

- One version for the core, so no compatibility matrix between kernel and
  components.
- Boundaries hold through the import test, not through packaging. Packaging alone
  would not enforce them, because in one environment any package can import any
  other.
- Splitting the core later is mechanical while the contracts hold.

## Rejected

- **Separate kernel and components packages now.** The cost is coordinated
  releases and a compatibility matrix between two core packages and every app.
  Every component imports kernel services (render, auth, preferences,
  permissions), so the split would mostly move imports around. And it would buy no
  enforcement the import test does not already give.
- **Apps inside the core package.** Taskline's UI could not be installed into
  another host.
