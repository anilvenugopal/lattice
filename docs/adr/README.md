# Architecture decision records

One file per decision: what was decided, why, what it costs, and what was rejected.
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) describes the resulting design.

A record is never rewritten after it is accepted. A later decision that changes it
is a new record that names the one it replaces.

| # | Decision | Status |
|---|---|---|
| [0001](0001-postgres-with-per-app-bindings.md) | Postgres only, with per-app database bindings | Accepted; bindings deferred (see its note) |
| [0002](0002-one-core-package-apps-as-packages.md) | One core package with enforced boundaries; each app its own package | Accepted |
| [0003](0003-app-manifest-and-contracts.md) | Apps plug in through a manifest and kernel contracts | Accepted |
| [0004](0004-charts-chartjs.md) | Charts with Chart.js and its plugins | Accepted |
| [0005](0005-graphs-xyflow-web-component.md) | Graphs with Svelte Flow compiled to a web component | Accepted |
| [0006](0006-taskline-as-lattice-app.md) | The taskline UI is a Lattice app, bundled or as an Ops console | Accepted; partly superseded by 0012 |
| [0007](0007-json-schema-forms.md) | Forms rendered from JSON Schema, JSON in and JSON out | Accepted |
| [0008](0008-grid-data-sources.md) | Grid rows come from data sources with keyset paging | Accepted in part (keyset paging) |
| [0009](0009-permissions.md) | Permissions declared by apps, grouped into roles | Accepted |
| [0010](0010-theming-and-overrides.md) | Theming and overrides: the host owns the brand, apps style only their own pages | Proposed |
| [0011](0011-integration-standards.md) | Integration standards: URN references, CloudEvents, published views, OpenAPI between processes | Accepted |
| [0012](0012-taskline-ui-and-contract.md) | Taskline UI on Taskline's published contract: views, async commands, no events | Accepted |
| [0013](0013-geoengine-and-maps.md) | Geospatial: a separate geoengine package, PostGIS, and a Lattice map component | Accepted |
| [0014](0014-timeline-component.md) | Timelines: a TimelineSpec component drawn in HTML | Accepted |
| [0015](0015-chart-colours.md) | Chart colours: one hue by default, colour only where it means something | Accepted |

Statuses: Proposed, Accepted, Superseded by NNNN.
