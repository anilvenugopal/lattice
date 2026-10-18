# Lattice: Architecture

Lattice is a platform that web applications run on. It supplies sign-in,
users and permissions, navigation, search, audit, preferences, and a set of UI
components (grid, form, chart, graph). Applications are separate Python
packages that plug into it. One deployment, a **host**, chooses which
applications it runs.

This document describes the target design. Decisions and their reasons are in
[`docs/adr/`](adr/README.md). What exists today, and the order of the work to
reach the target, are in the last two sections.

## 1. Terms

| Term | Meaning | Example |
|---|---|---|
| **Kernel** | The platform services every application uses: application registry, auth, users, permissions, navigation, search, references, events, audit, preferences, settings, database bindings, migrations | `lattice.kernel` |
| **Component** | A UI element any page can embed, declared in Python, rendered by a template, driven by its own JS and CSS | grid, form, chart, graph, stepper, tree, timeline, record view |
| **Application (app)** | A Python package that adds pages, data and behaviour through an `AppManifest` | `lattice-taskline`, `lattice-incidents`, `strategiq-web` |
| **Service app** | An app other apps use: it offers panels, search, references and events, and has no business domain of its own | Jobs (taskline), Incidents, Notifications |
| **Business app** | An app for one business domain. It may use service apps | strategiq, a risk workbench |
| **Host** | A deployable web application: Lattice plus a chosen list of apps plus configuration | `strategiq-web`, an Ops console |
| **Binding** | A named database connection an app declares, mapped to a URL by the host | `taskline.default`, `taskline.prod` |
| **Reference** | A typed pointer to a record in any app: `kind:id` | `submission:123`, `job_run:9f2…` |
| **Record panel** | A section an app contributes to other apps' record pages | the "Jobs" panel on a strategiq document |

## 2. Layers

```
┌──────────────────────────────────────────────────────────────────┐
│ Host            strategiq-web · ops-console · demo               │
│                 chooses apps, bindings, settings                 │
├──────────────────────────────────────────────────────────────────┤
│ Business apps   strategiq · risk workbench · …                   │
├──────────────────────────────────────────────────────────────────┤
│ Service apps    taskline (Jobs) · incidents · notifications      │
├──────────────────────────────────────────────────────────────────┤
│ Components      grid · form · chart · graph · stepper · tree ·   │
│                 timeline · record view                           │
├──────────────────────────────────────────────────────────────────┤
│ Kernel          app registry · auth/OIDC · users · permissions · │
│                 nav · search · references · events · audit ·    │
│                 preferences · settings · bindings · migrations   │
└──────────────────────────────────────────────────────────────────┘
```

Rules:

1. Imports point down only. Components import the kernel; apps import
   `lattice.api`; nothing in Lattice imports an app.
2. Apps never import each other. They cooperate through the kernel contracts in
   section 4: references, record panels, events and the registries.
3. Business apps and service apps are built the same way. The difference is
   who uses them, not how they plug in.
4. A host contains no feature code. It is configuration: the app list, bindings
   and settings.

## 3. Packages and repository layout

Lattice is one package, `lattice`, with enforced internal boundaries. Each app
is its own package. Reasons: [ADR 0002](adr/0002-one-core-package-apps-as-packages.md).

```
lattice/                         (this repository, a uv workspace)
  lattice/                       the core package
    api.py                       the only module apps import
    kernel/                      auth, users, nav, audit, preferences, settings, db,
                                 web (render, flash, toast), icons, slots, css_rules;
                                 later: permissions, references, events, bindings
    components/                  grid/, search/ (Ctrl+J), tiles, manifest (AppManifest);
                                 later: form/, chart/, graph/, stepper/, tree/, record/
    platform/                    Lattice's own apps: home, account, admin
    host.py                      create_app and the checks on every app
    cli.py                       lattice migrate | create-user | seed | dev
    testing.py                   pytest fixtures for core and app tests
    static/css/                  the five CSS layers
    templates/                   shell layout, macros
  apps/
    demo/                        today's examples (work queue, jobs, inbox)
    taskline/                    lattice-taskline (ADR 0006)
    incidents/                   lattice-incidents
  frontend/
    graph/                       the one built component (ADR 0005)
  hosts/
    demo/                        runs Lattice with the demo app
  docs/
```

Business apps live in their own repositories and depend on `lattice` and the
service apps they need. For example, strategiq adds a `strategiq-web` package
and a host.

### Boundaries inside `lattice`

Import contracts, checked by a test (`import-linter`), in the same way
`tests/test_css_architecture.py` checks the CSS:

| Contract | Rule |
|---|---|
| Layers | `kernel` ← `components` ← `platform` ← `host` ← `api`, `cli`, `testing`; each imports only the layers below it |
| Public entry point | Apps import only `lattice.api`. Everything else is internal and may change without notice |
| Independence | `apps.*` packages never import each other |
| Component isolation | One component imports another only through its spec (a chart may take a grid's source), never its internals |

`lattice.api` re-exports the stable names: `AppManifest`, `GridSpec`,
`Column`, `Action`, `FormSpec`, `ChartSpec`, `GraphSpec`, `ReferenceKind`,
`RecordPanel`, `Permission`, `render_page`, `flash`, `toast`, and the
dependency functions (`current_user`, `require`, `get_db`). Removing or
changing one of these is a breaking change and needs a version bump.

## 4. How apps plug in

### 4.1 The app manifest

Every app package exposes one `AppManifest`. The host passes the manifests to
`create_app`.

```python
# lattice_taskline/__init__.py
APP = AppManifest(
    key="taskline",                         # URL prefix, template folder, settings prefix, permission prefix
    label="Jobs",
    icon="taskline:app",                    # from the app's own icons; follows the theme
    icons={"app": "<path …/>"},
    help_url="https://…/taskline",          # listed in the Help menu
    permissions=[Permission("taskline.view"), Permission("taskline.operate")],
    bindings=["default"],                   # or one per instance, see 6.4
    nav=[...],                              # NavNodes, under /taskline/...
    routers=[...],
    grids=[...], search=[...], tiles=[...],
    reference_kinds=[ReferenceKind("job_run", resolve=...)],
    record_panels=[RecordPanel("Jobs", kinds="*", render=...)],
    publishes=["job.failed", "job.succeeded"],
    subscribes={},
    migrations=None,                        # taskline migrates its own schema
    settings=TasklineSettings,              # pydantic, env prefix LATTICE_TASKLINE_
    background=None,                        # optional async task started with the host
)

# host: strategiq-web
app = create_app(apps=[lattice_taskline.APP, lattice_incidents.APP, strategiq_web.APP],
                 host_dir=Path(__file__).parent)      # templates/, static/theme.css
```

What `create_app` does with each manifest:

| Manifest field | Kernel registry it feeds |
|---|---|
| `nav` | Navigation: rail, sidebar, breadcrumbs, Ctrl+J pages. Rail order follows the app list |
| `routers` | Mounted under `/{key}` |
| `grids`, `search`, `tiles` | Grid registry, search providers, home tiles |
| `permissions` | Permission catalogue shown on Administration › Roles |
| `reference_kinds` | Reference registry (4.2) |
| `record_panels` | Panel registry (4.3) |
| `publishes`, `subscribes` | Event bus (4.4) |
| `bindings`, `migrations` | Database bindings and `lattice migrate` (section 5) |
| templates, static | Template search order host → app (`{key}/…`) → core; static files at `/static/{key}/` (4.6) |
| `icon`, `icons`, `help_url` | The app's icons (`icon("{key}:name")`); its entry in the Help menu (4.6) |
| `settings` | Validated at startup; a missing required setting stops the host with one clear message |

An app's CSS declares `@layer components { … }`, so it joins the five-layer
cascade without being imported by Lattice's `app.css`. What an app may style is
limited (4.6).

### 4.2 References

A reference is `kind:id`. An app registers each kind it owns with a resolver:

```python
ReferenceKind("submission", label="Submission",
              resolve=lambda db, user, id: Resolved(title=..., url=f"/strategiq/submissions/{id}",
                                                    preview=...))
```

Any template can then show a reference with `{{ ref("submission:123") }}`, which
renders a link with the record's title and the same preview Ctrl+J shows.
Anything stored across apps is stored as a reference: taskline's job references,
incidents' affected records, comments and attachments.

Taskline already records references with a kind, label and link
(`jobs.job_reference`, `jobs.reference_kind`). The taskline app maps them onto
this registry, so a job started for `document:doc-1` links back to strategiq's
document page.

### 4.3 Record panels and the record view

The record view component is the standard detail page: header with status and
actions, properties, and a set of panels. An app's own panels come first. Panels
contributed by other apps follow, matched on the record's reference kind:

| Contributing app | Panel | Shows |
|---|---|---|
| taskline | Jobs | Runs that carry this record as a reference, with status and a link to the run |
| incidents | Incidents | Open and recent incidents naming this record |
| comments (later) | Activity | Comments and audit history |

A business app gets these panels by rendering its detail page with the record
view. It does not need code for each service app.

### 4.4 Events

An in-process event bus. An app publishes after its transaction commits:

```python
events.publish("job.failed", ref="job_run:9f2…", data={"job": "ingest_document", "error": "..."})
```

Subscribers run in the publishing process, after the commit. For example,
incidents subscribes to `job.failed` to open or update an incident, and
notifications subscribes to `incident.created`. Event names are
`{app}.{event}`, and payloads are small: references and a few fields, never
whole records.

There is no delivery guarantee across a crash between the commit and the
subscriber. If an event must survive that, the publisher adds an outbox table
and the event is sent from it. Add that only for an event that needs it.

### 4.5 Permissions

Apps declare permissions (`taskline.operate`). Roles are named sets of
permissions that administrators edit. Routes, nav nodes, grid actions, search
providers and record panels check permissions, never role names.
[ADR 0009](adr/0009-permissions.md).

Some permissions apply per instance. In the Ops console, a user may operate the
dev taskline but only view prod, so permissions can be scoped to a binding:
`taskline.operate@prod`.

### 4.6 Theming and overrides

The host owns the brand. Apps style only their own pages.
[ADR 0010](adr/0010-theming-and-overrides.md).

- **Precedence.** Every lookup (templates, icons, tokens) goes host, then app,
  then core. Each level overrides only what it owns. No level edits or copies
  core files.
- **What the host sets:**
  - the name, logos and favicon (settings);
  - brand colours and fonts, in a `theme.css` that may redefine only an allowed
    list of semantic tokens, for both light and dark;
  - the icon set;
  - whole sign-in, error and home pages.
- **What an app sets:**
  - an app icon (light and dark) for its rail entry, Ctrl+J source and tiles;
  - an `--app-accent` and its own component tokens, scoped under
    `[data-app="{key}"]`, which the shell puts on the app's pages;
  - icons in its own namespace (`icon("taskline:dag")`);
  - templates in its own folder.

  An app cannot restyle the shell or override core templates.
- **Named slots** take small additions without a template override:
  `topbar.end`, `statusbar.start`, `statusbar.end`, `signin.footer`,
  `home.sections`, `help.menu`.
- **Checks.** The CSS architecture test checks host and app stylesheets against
  these rules. The app loader rejects templates, icons or slots outside an app's
  namespace.

## 5. Data

Postgres only. [ADR 0001](adr/0001-postgres-with-per-app-bindings.md).

- **Bindings.** Each app declares one or more named bindings. The host maps each
  to a URL (`LATTICE_TASKLINE_DATABASE_URL`, or `…_PROD_DATABASE_URL`); an
  unmapped binding uses Lattice's own database. Apps can therefore share one
  database or each have their own, and that is configuration only.
- **Schemas.** Each app owns one Postgres schema: `lattice` for the kernel,
  `jobs` for taskline (taskline's own choice), `incidents`, `strategiq`. An app
  never writes another app's schema.
- **Migrations.** `lattice migrate` runs each app's migrations against its
  binding, with Alembic's version table inside that app's schema. An app whose
  library migrates itself, such as taskline (`taskline migrate`), declares that
  instead.
- **No cross-app keys.** Apps refer to each other's records by reference, never
  by foreign key, because they may be in different databases.
- **Transactions end at the binding.** A write in app A and the kernel's audit
  record are separate commits when they use different databases. Audit records
  and events are written after the app's commit.
- **Sync and async.** A binding gives both a sync and an async SQLAlchemy engine
  from one URL (psycopg 3). Kernel code stays sync; an app may use async routes
  and async grid sources (taskline's read API is async).
- **Tests** create a throwaway Postgres database per test, as taskline's tests
  already do.

## 6. Components

All components share a pattern the grid already follows:

- a Python spec that declares the component;
- shared endpoints keyed by the spec (`/_grid/{key}/…`);
- a Jinja macro to place it on a page;
- an Alpine component for client behaviour;
- one CSS file in the components layer.

Every component checks the same permissions and uses the same action model.

### 6.1 Grid

Today's grid ([Grids](../lattice/help/developer/building-apps/grids.md)) with one change: the rows come from a
**data source** instead of only a SQLAlchemy query.
[ADR 0008](adr/0008-grid-data-sources.md).

```python
class GridSource(Protocol):
    def count(self, ctx, state) -> int: ...
    def page(self, ctx, state, cursor) -> Page: ...      # keyset cursor, not offset
    def by_ids(self, ctx, ids) -> list[dict]: ...         # the access boundary for actions
```

- `SqlSource(query)` is today's behaviour and stays the default.
- An async source wraps an async API, such as taskline's `Queries`.
- A merged source combines several sources and sorts the result by one key. The
  taskline Ops console uses it to list runs from several instances together.
  This is why paging is keyset (a cursor), not offset: offsets cannot be merged
  across databases.

### 6.2 Charts

Chart.js 4 with plugins, vendored like htmx (no build).
[ADR 0004](adr/0004-charts-chartjs.md).

| Need | Plugin |
|---|---|
| Time series, zoom and pan | time scale + `chartjs-adapter-date-fns`, `chartjs-plugin-zoom` |
| Maps (choropleth, bubble) | `chartjs-chart-geo` with vendored TopoJSON (world, countries) |
| Calendar heatmap, matrices | `chartjs-chart-matrix` |
| Treemap, flows | `chartjs-chart-treemap`, `chartjs-chart-sankey` |
| Thresholds and markers | `chartjs-plugin-annotation` |

```python
ChartSpec(key="runs_per_day", source=RUNS_GRID, kind="bar",
          x=Time("created_at", unit="day"), y=Count(), group_by="status",
          tones_from=RUNS_GRID.column("status"))
```

- **Filter linking.** A chart built on a grid's source can share that grid's
  view, filters and search on a page. Filter the grid and the chart follows, as
  in Foundry Workshop.
- **Aggregation runs in the database** (group by, date truncation), not in the
  browser.
- **Colours are read from the CSS tokens**, so charts follow dark mode and the
  tone of each status.

### 6.3 Graphs, flows and trees

Three components, from simplest to richest:

| Component | Built with | For |
|---|---|---|
| **Stepper** | HTML and CSS only | Linear flows: a taskline job's steps (v1 chains are sequential), process stages |
| **Tree** | HTML and CSS, collapsible | Hierarchies: taskline lineage (parent run → child runs), dependency trees without shared nodes |
| **Graph** | Svelte Flow (xyflow) compiled to a web component, with dagre layout | DAGs and process maps where users navigate and act from the graph |

The graph component:
[ADR 0005](adr/0005-graphs-xyflow-web-component.md).

```html
<lt-graph spec='{{ graph | tojson }}'></lt-graph>
```

- **Nodes carry references.** Clicking a node opens its preview, or its record,
  through the reference registry.
- **Node actions use the grid's action model** (`actions_for(user)`,
  `applies(row)`) and the same action endpoint, so "Retry task" means the same
  thing in a grid and in a graph.
- **It is built once** in `frontend/graph/` (Vite, Svelte, xyflow, dagre), and
  the output file is committed to `static/`. App authors never run npm.
- **A spike comes first.** Before the graph is adopted, a spike must show:
  - the web component inside htmx swaps;
  - dark mode from the CSS tokens;
  - a 200-node DAG with automatic layout;
  - keyboard focus;
  - its size.

  React Flow is the fallback if the spike fails.

### 6.4 Forms (JSON in, JSON out)

[ADR 0007](adr/0007-json-schema-forms.md).

- **One schema language: JSON Schema 2020-12.** A Pydantic model provides one
  through `model_json_schema()`. A template JSON is an example, and a schema is
  inferred from it.
- **Schema resolution order:**
  1. an explicit `schema=` parameter;
  2. the document's `$schema`;
  3. a registry match on a type or kind field;
  4. a schema inferred from the document, which renders it as it is.

  The user can apply a different schema, and the form re-renders with it.
- **Round trip.** Fields the schema does not describe are shown under "Other
  fields" and returned unchanged. Data is never dropped because a schema is
  narrower than the document.
- **Missing fields.** With a schema, its fields appear even when the document
  lacks them. Without one, "Add field" (a name and a type) adds a property.
- **Layout hints are kept apart** in a small `ui` object (order, sections,
  widget, label, help), so the schema stays a plain JSON Schema.
- **Rendering is server-side.** Recursive macros cover object, array, string
  (with formats), number, integer, boolean, enum, `$ref`/`$defs`, and `oneOf`
  with a discriminator. A raw JSON tab is the fallback for anything else.
  Validation on the server (the `jsonschema` library) is authoritative; HTML
  constraints only help the user.
- **CRUD through `FormSpec(schema, ui, load, save)`.** The spec is
  storage-independent: `load` returns a dict, `save` receives one.
- **Document store.** `lattice.kernel.documents` stores mixed-shape records
  (kind, schema id and version, JSONB data, audit). It is for configuration,
  templates and low-volume records, not for business entities that are
  filtered, joined or reported on.
- **Form builder, later.** It is the form renderer applied to a schema that
  describes the supported subset of JSON Schema, with a live preview. Build it
  when two apps need it.

### 6.5 Other components

- **Timeline:** the audit and event history (exists as the `timeline` macro).
- **Stat tiles:** home and dashboard counts (exist).
- **Record view:** section 4.3.

## 7. The taskline app

`lattice-taskline` is the admin UI that taskline's requirements describe
(FR-22, FR-35, FR-44). It also answers taskline's open question 2: the UI is a
Lattice app, not part of the taskline package.
[ADR 0006](adr/0006-taskline-as-lattice-app.md).

- **It uses taskline's public API only.** It reads through `taskline.queries`;
  cancel, retry and schedule changes go through taskline's commands. It never
  reads the `jobs` tables directly, so taskline can change its schema.
- **Pages:**
  - Runs (grid; filters for status, producer, job, correlation id, reference, date);
  - Run detail (stepper of task instances, event timeline, references, cancel and retry);
  - Lineage (tree, then graph);
  - Queues and workers (counts, oldest waiting, live workers, reaper alive);
  - Schedules (grid plus forms: create, pause, resume, delete);
  - Run job (a form generated from the job's declared inputs).
- **Contributions to other apps:**
  - a Jobs record panel for any record kind;
  - a `job_run` reference kind;
  - a Ctrl+J provider;
  - home tiles (running, failed);
  - events `job.failed` and `job.succeeded`, from taskline hooks.
- **Two modes, one package:**
  - **Bundled.** Strategiq's host includes it with one binding: strategiq's
    taskline database.
  - **Ops console.** A host includes it with several bindings, one per taskline
    instance. Every row id carries its instance (`prod/9f2…`), the grids have an
    Instance column and filter, and lists across instances use a merged source
    (6.1).
- **Python 3.14.** Taskline requires it, so hosts that include this app run on
  3.14. Lattice targets 3.14.

## 8. The incidents app (outline)

`lattice-incidents` collects problems from every app in one place.

- **Sources:**
  - events (`job.failed` from taskline, and others);
  - manual entry;
  - an ingestion API with tokens, for systems outside Lattice.
- **Deduplication** by a fingerprint (source, kind, reference), so repeated
  failures update one incident instead of opening many.
- **The incident record:**
  - status (open, acknowledged, resolved);
  - severity and owner;
  - affected references;
  - a timeline of occurrences and notes.
- **Contributions:**
  - an Incidents record panel on any record it names;
  - an `incident` reference kind;
  - a Ctrl+J provider;
  - a home tile;
  - events `incident.created` and `incident.resolved` for notifications.

Its own design document comes before it is built.

## 9. Other planned features

In priority order. Each will get its own design note when it is started.

1. **Record view framework** (4.3). Panels, references and the incidents and
   taskline integrations depend on it.
2. **Saved views for grids**, personal and shared, also used by charts.
3. **Notifications** service app: in-app notifications from events, email later.
   Today's Inbox example becomes its UI.
4. **Comments and attachments** on any record, keyed by reference.
5. **API tokens and per-app JSON APIs**, for incident ingestion and calls
   between services.
6. **Lattice's own background work runs on taskline**, for example large CSV
   exports and bulk actions. The demo Jobs grid is then replaced by the real one.

## 10. Where Lattice is today

Step 1 (kernel restructure) is done. What remains:

| Area | Today | Target |
|---|---|---|
| Package | `lattice` core, `apps/demo`, `hosts/demo`, `lattice.api`, import contracts | Unchanged |
| Apps | `AppManifest` and `create_app(apps=[…])` with namespace checks | + settings, bindings, permissions, references, panels, events per manifest |
| Database | SQLite default, one connection, one Alembic history | Postgres only, per-app bindings, schemas and migrations |
| Permissions | Roles only (`admin`, `editor`, `viewer`) | Permissions grouped into roles; per-binding scopes |
| Grid | SQLAlchemy query, offset paging, sync | Data sources, keyset paging, async sources |
| Cross-app | None needed yet | References, record panels, events |
| Components | Grid, Ctrl+J, tiles, macros, timeline, stats | + form, chart, stepper, tree, graph, record view |
| CSS | Five ITCSS layers; app stylesheets scoped by `data-app`; host theme limited to brand tokens; all checked | Unchanged; `--app-accent` read by core when an app needs an accent |
| Branding | Settings for name and logos; host folder (`theme.css`, page overrides); icon registry; named slots | Unchanged |
| Settings | `LATTICE_` prefix | + per-app prefixes (`LATTICE_{KEY}_`) |

## 11. Order of work

Each step ends with tests passing and the demo running, and each is reviewed
before the next starts.

1. **Kernel restructure.** Done.
   - `app/` becomes `lattice/` with `kernel/`, `components/` and `platform/`.
   - `lattice.api` and the import-contract test.
   - `AppManifest` and `create_app`.
   - Template search order, icon registry, named slots and `data-app` scoping
     ([ADR 0010](adr/0010-theming-and-overrides.md)), with the CSS test extended
     for host and app stylesheets.
   - The example features move to `apps/demo`.
   - The `lattice` CLI and `LATTICE_` settings.
2. **Postgres and bindings.**
   - Per-app schemas and migrations.
   - Postgres in a container for development, and test databases per test.
   - SQLite removed.
3. **Permissions** replace role checks.
4. **References, record panels, events,** and the record view.
5. **Grid data sources** with keyset paging and async sources.
6. **`lattice-taskline` spike** against strategiq's taskline:
   - runs grid and run detail with the stepper;
   - queues;
   - cancel and retry;
   - the Jobs panel on a strategiq record.
7. **Chart component** with the plugins.
8. **`<lt-graph>` spike** (Svelte Flow) on taskline lineage. Adopt it or fall
   back to React Flow.
9. **JSON form renderer** and the document store.
10. **Incidents app**, after its own design document.

## 12. Open questions

| # | Question | Notes |
|---|---|---|
| O-1 | Where do business apps live: their own repositories (recommended) or `apps/` here? | Own repositories keep Lattice free of business code |
| O-2 | How are Lattice and its apps distributed to other repositories: git dependencies or a private package index? | Git dependencies with tags work until there are several consumers |
| O-3 | Does the Ops console need its own sign-in, or does it use the same OIDC provider as the business hosts? | Affects how users and permissions are shared across hosts |
| O-4 | Who owns the reference kinds taskline already registers (`document`)? | Proposed: the business app registers the kind in Lattice; taskline only stores it |
