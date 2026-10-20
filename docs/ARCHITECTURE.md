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
| **Application (app)** | A Python package that adds pages, data and behaviour through an `AppManifest` | `taskline-ui`, `lattice-incidents`, `strategiq-web` |
| **Service app** | An app other apps use: it offers panels, search, references and events, and has no business domain of its own | Taskline UI, Incidents, Comments |
| **Business app** | An app for one business domain. It may use service apps | strategiq, a risk workbench |
| **Host** | A deployable web application: Lattice plus a chosen list of apps plus configuration | `strategiq-web`, an Ops console |
| **Binding** | A named database connection an app declares, mapped to a URL by the host | `taskline.default`, `taskline.prod` |
| **Reference** | A pointer to a record in any app: a URN, `urn:lattice:{kind}:{id}` (ADR 0011) | `urn:lattice:strategiq.submission:123`, `urn:lattice:taskline.run:9f2…` (built by Taskline UI) |
| **Record panel** | A section an app contributes to other apps' record pages | the "Jobs" panel on a strategiq document |

## 2. Layers

```
┌──────────────────────────────────────────────────────────────────┐
│ Host            strategiq-web · ops-console · showcase           │
│                 chooses apps, bindings, settings                 │
├──────────────────────────────────────────────────────────────────┤
│ Business apps   strategiq · risk workbench · …                   │
├──────────────────────────────────────────────────────────────────┤
│ Service apps    Taskline UI · comments · incidents               │
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
    showcase/                    the showcase: catastrophe response, on every component
  frontend/
    graph/                       the one built component (ADR 0005)
  hosts/
    showcase/                    runs Lattice with the showcase
  docs/
```

**Every other app has its own repository** and depends on `lattice` (and on
the service apps it needs):

| Repository | Holds | Depends on |
|---|---|---|
| `lattice` | The core package and the showcase apps | — |
| `taskline` | The job engine (a library, no UI) | — (never on Lattice) |
| `taskline-ui` | Taskline UI: the admin screens for Taskline, a Lattice app ([ADR 0012](adr/0012-taskline-ui-and-contract.md)) | `lattice`, `taskline` |
| `lattice-incidents` | The Incidents app | `lattice` |
| `strategiq`, … | Business apps and their hosts | `lattice`, and the service apps they use |

**How a repository depends on another:**

- **Releases:** a git tag (`lattice @ git+…@v0.4.0`) until there are several
  consumers, then a private package index.
- **Development:** an editable path source in `uv`
  (`lattice = { path = "../lattice", editable = true }`), so changes in Lattice
  are seen at once.

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
# taskline_ui/__init__.py (Taskline UI, in its own repository)
APP = AppManifest(
    key="taskline",                         # URL prefix, template folder, permission prefix
    label="Jobs",
    icon="taskline:app",                    # from the app's own icons; follows the theme
    icons={"app": "<path …/>"},
    permissions=[Permission("taskline.runs.view", …), Permission("taskline.runs.operate", …)],
    nav=[...],                              # NavNodes, under /taskline/...
    routers=[...],
    grids=[...], search=[...], tiles=[...], # grids read Taskline's taskline_api views
    references=[ReferenceKind("taskline.run", "Run", resolve_run)],
    panels=[RecordPanel("taskline.jobs", "Jobs", "taskline/jobs_panel.html", kinds="*", …)],
    sql=HERE / "sql",                       # named queries over taskline_api; Taskline migrates itself
    background=None,                        # optional async task started with the host
)

# host: strategiq-web
app = create_app(apps=[strategiq_web.APP, taskline_ui.APP, lattice_comments.APP],
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

A reference is a URN, `urn:lattice:{kind}:{id}`, whose kind starts with the
owning app's key ([ADR 0011](adr/0011-integration-standards.md)). An app
registers each kind it owns with a resolver:

```python
ReferenceKind("strategiq.submission", label="Submission",
              resolve=lambda db, user, id: Resolved(title=..., url=f"/strategiq/submissions/{id}",
                                                    preview=...))
```

Any template can then show a reference with `{{ ref("urn:lattice:strategiq.submission:123") }}`, which
renders a link with the record's title and the same preview Ctrl+J shows.
Anything stored across apps is stored as a reference: taskline's job references,
incidents' affected records, comments and attachments.

Taskline already records references with a kind, label and link
(`jobs.job_reference`, `jobs.reference_kind`). The taskline app maps them onto
this registry, so a job started for `urn:lattice:strategiq.document:doc-1` links
back to strategiq's document page.

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

Events are CloudEvents ([ADR 0011](adr/0011-integration-standards.md)): a
`type` such as `comments.added`, a `subject` that is the record's URN, and
small `data`. Inside a host they travel on an in-process bus. An app publishes
inside its transaction, and the event is delivered after the commit:

```python
db.publish("comments.added", subject="urn:lattice:showcase.claim:42", data={"comment_id": 7})
```

Another process's state is read, not streamed: an app that must react to
Taskline's finished runs reads `taskline_api.run` on a timer for a time window
and remembers which runs it has handled ([ADR 0012](adr/0012-taskline-ui-and-contract.md)).
Events from remote systems will arrive over HTTP, in the CloudEvents HTTP
binding, when API tokens exist.

Subscribers run in the publishing process, after the commit. For example,
the showcase subscribes to `comments.added` to tell a claim's handler, and
notifications will subscribe to `incidents.created`. Event types are
`{app}.{event}`, and data is small: references and a few fields, never whole
records.

There is no delivery guarantee across a crash between the commit and the
subscriber. A reaction that must not be missed reads state instead, as above.

### 4.5 Permissions

Apps declare permissions (`taskline.operate`). Roles are named sets of
permissions that administrators edit in Administration › Roles; the admin role
has every permission. Routes, nav nodes, grids, grid actions, search providers,
help topics and record panels check permissions, never role names.
[ADR 0009](adr/0009-permissions.md). Built in step 3, without binding scopes.

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
    list of semantic tokens, for both light and dark, and load font files from
    the host folder;
  - the favicon;
  - the icon set;
  - whole sign-in, error and home pages, and the notification email templates.
- **What an app sets:**
  - an app icon (light and dark) for its rail entry, Ctrl+J source and tiles;
  - an accent, named as a tone in its manifest, which marks its rail entry and
    page titles (`--app-accent` on its pages), and its own component tokens,
    scoped under `[data-app="{key}"]`, which the shell puts on the app's pages;
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

Postgres 18 only (18 since [ADR 0012](adr/0012-taskline-ui-and-contract.md), for Taskline). [ADR 0001](adr/0001-postgres-with-per-app-bindings.md), as
narrowed by the step 2 decisions (18 October 2026, recorded in
[Decisions and direction](../lattice/help/developer/architecture/decisions.md)).

- **Plain SQL, no ORM.** Every statement is a named query in a `sql/<area>.sql`
  file, run through `Db` on SQLAlchemy Core with the psycopg 3 driver. Only the
  grid engine and the migration runner build SQL in code. Tests and lint enforce
  this ([Data and audit](../lattice/help/developer/building-apps/data-and-audit.md)).
- **One database, one engine.** Lattice and its apps share one database and one
  connection pool, created once. Each request is one transaction.
- **Schemas.** Each app owns one Postgres schema, named after its key: `lattice`
  for the kernel, `showcase`, `incidents`, `strategiq`; taskline keeps `jobs`. An app
  never writes another app's schema; it may read Lattice's (a person's name from
  `lattice.app_user`).
- **Migrations.** Plain `.sql` files in each app's `sql/schema/`, applied in
  order by `lattice migrate`, with a `_schema_version` table in each schema, in
  the style of taskline's runner. An app whose library migrates itself, such as
  taskline (`taskline migrate`), declares that instead.
- **No cross-app keys.** Apps refer to each other's records by reference, never
  by foreign key.
- **Bindings, later.** A separate database for one app (the host maps a named
  binding to its own URL) is not built. It comes when an app needs one, such as
  an Ops console over several Taskline instances (deferred, ADR 0012). Writes in two
  databases are then separate commits, and audit records and events are written
  after the app's commit.
- **Sync, with async actions.** Lattice's database access is sync. Grid actions
  may be `async`, so an app can await a library's async API (Taskline's
  commands, which use Taskline's own connection). Lattice has no async engine.
- **Tests** create a Postgres database per test, copied from a template migrated
  once per run.

## 6. Components

All components share a pattern the grid already follows:

- a Python spec that declares the component;
- shared endpoints keyed by the spec (`/_grid/{key}/…`);
- a Jinja macro to place it on a page;
- an Alpine component for client behaviour;
- one CSS file in the components layer.

Every component checks the same permissions and uses the same action model.

### 6.1 Grid

Today's grid ([Grids](../lattice/help/developer/building-apps/grids.md)). Proposed, not built: rows from a
**data source** instead of only a named SQL query
([ADR 0008](adr/0008-grid-data-sources.md)). Taskline UI doesn't need it, since
it reads Taskline's views with ordinary grids; it waits for an Ops console over
several databases.

```python
class GridSource(Protocol):
    def count(self, ctx, state) -> int: ...
    def page(self, ctx, state, cursor) -> Page: ...      # keyset cursor, not offset
    def by_ids(self, ctx, ids) -> list[dict]: ...         # the access boundary for actions
```

- `SqlSource(query)` is today's behaviour and stays the default.
- A merged source combines several sources and sorts the result by one key. The
  taskline Ops console uses it to list runs from several instances together.
  This is why paging is keyset (a cursor), not offset: offsets cannot be merged
  across databases.

### 6.2 Charts

Built in step 5 ([Charts](../lattice/help/developer/building-apps/charts.md)).
Chart.js 4 with plugins, vendored and loaded on first use.
[ADR 0004](adr/0004-charts-chartjs.md).

| Need | Plugin |
|---|---|
| Time series, zoom and pan | time scale + `chartjs-adapter-date-fns`, `chartjs-plugin-zoom` |
| World map (choropleth) | `chartjs-chart-geo` with vendored TopoJSON (Natural Earth countries) |
| Calendar heatmap | `chartjs-chart-matrix` |
| Treemap, flows | `chartjs-chart-treemap`, `chartjs-chart-sankey` |
| Thresholds | `chartjs-plugin-annotation` |

```python
ChartSpec(key="showcase.claims_per_day", title="Claims per day", source=CLAIMS_GRID,
          kind="bar", x=Time("reported_at", "day"), series="severity", stacked=True)
```

- **A chart's source is a GridSpec.** The grid's query, view, filters, search
  and fixed filters narrow the rows, so the grid's query stays the access
  boundary.
- **Filter linking.** A chart on the same page as its grid follows the grid's
  view, filters and search, as in Foundry Workshop.
- **Aggregation runs in the database** (`GROUP BY`, `date_trunc`); the largest
  categories are kept and the rest add up to "Other".
- **Colours come from `--chart-*` tokens**, and a series on a status column
  takes that column's tones, in light and dark.

### 6.3 Graphs, flows and trees

Built in step 5 ([Flows](../lattice/help/developer/building-apps/flows.md)).

| Component | Built with | For |
|---|---|---|
| **Stepper** | HTML and CSS only | Linear flows: a taskline job's steps (v1 chains are sequential), process stages |
| **Tree** | HTML and CSS, collapsible | Hierarchies: taskline lineage (parent run → child runs), dependency trees without shared nodes |
| **Graph** | Svelte Flow (xyflow) compiled to a web component, with dagre layout | DAGs and process maps where users navigate and act from the graph |

The graph component, `<lt-graph>`:
[ADR 0005](adr/0005-graphs-xyflow-web-component.md), accepted after its spike.

- **Node actions are a grid's actions** (`actions_for(user)`, `applies(row)`),
  read per node through the grid's query and run through the grid's action
  endpoint, so "Retry task" means the same thing in a grid and in a graph.
- **Nodes link to records** (`href`). Opening a reference's preview through the
  reference registry comes with step 7.
- **It is built once** in `frontend/graph/` (Vite, Svelte, xyflow, dagre), and
  the output file is committed to `static/`. App authors never run npm.
- **Spike results:** works in htmx swaps; dark mode from the tokens; a 200-node
  DAG in about half a second; keyboard focus; 327 KB (100 KB compressed).

### 6.4 Forms (JSON in, JSON out)

Built in step 5 ([Forms from JSON Schema](../lattice/help/developer/building-apps/json-forms.md)).
[ADR 0007](adr/0007-json-schema-forms.md), accepted.

- **One schema language: JSON Schema 2020-12.** A Pydantic model provides one
  through `model_json_schema()`. A template JSON is an example, and a schema is
  inferred from it.
- **Schema resolution order:**
  1. an explicit `schema=` parameter;
  2. the document's `$schema`;
  3. a registered schema (`SchemaDef`), by id;
  4. a schema inferred from the document, which renders it as it is.

  With `switchable=True` the user can apply another registered schema, and the
  form re-renders with it.
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
- **`FormSpec(key, schema, ui)` is storage-independent.** `build_form` draws
  a document; `parse_form` reads the post back and validates it; the app's
  route loads and saves. Edits that change the form's shape post to
  `/_form/{key}/render`.
- **Document store.** `lattice.document` stores mixed-shape records (kind,
  schema version, title, JSONB data, audit), declared as `DocumentKind`s. It is
  for configuration, templates and low-volume records, not for business
  entities that are filtered, joined or reported on. A grid of one kind binds
  the kind with `GridSpec.params`.
- **Form builder, later.** It is the form renderer applied to a schema that
  describes the supported subset of JSON Schema, with a live preview. Build it
  when two apps need it.

### 6.5 Other components

- **Record page:** `RecordPage` on a GridSpec: header with status and the
  grid's row actions, properties from the grid's columns, the app's panels and
  the audit history ([Record pages](../lattice/help/developer/building-apps/record-pages.md)).
  Panels from other apps (section 4.3) come with step 7.
- **Saved grid views:** a user's grid state under a name, shared with everyone
  by holders of `lattice.views.share`.
- **Timeline:** the audit and event history (the `timeline` macro).
- **Stat tiles:** home and dashboard counts.

## 7. Taskline UI

Taskline UI (`taskline-ui`, package `taskline_ui`, app key `taskline`) is the
admin UI that Taskline's requirements describe (FR-22, FR-35). It is a Lattice
app in its own repository, built only from Lattice's components and Taskline's
published contract ([ADR 0012](adr/0012-taskline-ui-and-contract.md), which
updates [ADR 0006](adr/0006-taskline-as-lattice-app.md)).

```text
   Taskline UI ──uses──► Lattice    (lattice.api)
        │
        └─────uses──► Taskline      (taskline_api views; async commands in taskline.api)

   Lattice  ✗  never imports Taskline
   Taskline ✗  never imports Lattice or Taskline UI
```

- **Reads** the `taskline_api` views (`run`, `task`, `reference`, `event`,
  `queue`, `worker`, `instance`, later `schedule`) with Lattice grids and named
  queries. Never the `jobs` tables.
- **Acts** through Taskline's async commands (`cancel_run`, `retry_run`,
  `requeue`, `submit_job`) from async grid actions, passing the user as `actor`.
  They commit in Taskline's own transaction; Lattice's audit record follows.
- **No events.** Taskline publishes none.
- **Pages:**
  - Runs (grid; filters for status, producer, job, correlation id, reference, date);
  - Run detail (record page: stepper of tasks, event timeline, references, cancel and retry);
  - Lineage (tree, then graph);
  - Queues and workers;
  - Schedules, when Taskline's scheduler exists;
  - Run job (a form from the job's input JSON Schema).
- **Contributions to other apps:** a Jobs record panel, the `taskline.run`
  reference kind, a Ctrl+J provider and home tiles.
- **One instance per host for now.** An Ops console over several instances is
  deferred.
- **Postgres 18 and Python 3.14,** as Taskline requires.

## 8. The incidents app (outline)

`lattice-incidents` collects problems from every app in one place.

- **Sources:**
  - failed Taskline runs, read from `taskline_api.run` on a timer;
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
  - events `incidents.created` and `incidents.resolved` for notifications.

Its own design document comes before it is built.

## 9. Other planned features

Not yet placed in the order of work. Each will get its own plan when it is started.

1. **Notifications**: in Lattice's core, not a service app (ADR 0016). Phase 1, the
   in-app inbox, `notify()`, kinds tied to events and following records, is built;
   email with preferences, then webhooks, follow.
2. **Attachments** on any record, keyed by reference (comments exist, step 8).
3. **API tokens and per-app JSON APIs** (OpenAPI, ADR 0011), for incident
   ingestion and calls between services.
4. **Lattice's own background work on Taskline**, when the host includes it:
   large CSV exports and bulk actions.

## 10. Where Lattice is today

Steps 1 to 8 are done. What remains:

| Area | Today | Target |
|---|---|---|
| Package | `lattice` core, `apps/showcase`, `hosts/showcase`, `lattice.api`, import contracts | Ecosystem apps in their own repositories |
| Apps | `AppManifest` and `create_app(apps=[…])` with namespace checks | + settings, bindings, permissions, references, panels, events per manifest |
| Database | Postgres 18; one database, a schema and SQL migrations per app; named SQL queries, no ORM | Unchanged; bindings to separate databases when an app needs one |
| Permissions | Declared by apps, grouped into roles that administrators edit | + per-binding scopes |
| Grid | Named SQL query, keyset paging, a time limit, sync | Data sources, async sources |
| Cross-app | URN references with resolvers, record panels, CloudEvents on an in-process bus ([ADR 0011](adr/0011-integration-standards.md)) | CloudEvents over HTTP, with API tokens |
| Components | Grid with saved views, charts, record page with other apps' panels, JSON Schema forms and the document store, stepper, tree, graph; Ctrl+J, help, tiles, macros, timeline | Unchanged |
| CSS | Five ITCSS layers; app stylesheets scoped by `data-app`; host theme limited to brand tokens and its own fonts; an app accent named as a tone; all checked (ADR 0010) | Unchanged |
| Branding | Settings for name and logos; host folder (`theme.css`, page overrides); icon registry; named slots | Unchanged |
| Settings | `LATTICE_` prefix | + per-app prefixes (`LATTICE_{KEY}_`) |

## 11. Order of work

Each step ends with tests passing and the showcase running, and each is reviewed
before the next starts.

1. **Kernel restructure.** Done.
   - `app/` becomes `lattice/` with `kernel/`, `components/` and `platform/`.
   - `lattice.api` and the import-contract test.
   - `AppManifest` and `create_app`.
   - Template search order, icon registry, named slots and `data-app` scoping
     ([ADR 0010](adr/0010-theming-and-overrides.md)), with the CSS test extended
     for host and app stylesheets.
   - The example features move to `apps/showcase`.
   - The `lattice` CLI and `LATTICE_` settings.
2. **Postgres and plain SQL.** Done
   ([plan](plans/step-2-postgres-plain-sql.md)).
   - Postgres 17 only, a schema and plain SQL migrations per app; SQLite and
     Alembic removed.
   - Named SQL queries with no ORM, through one shared engine; one transaction
     per request.
   - Postgres in a container for development, a database per test.
   - A time limit on grid queries; the grids' plans checked with `EXPLAIN
     ANALYZE`. Grid search keeps joined columns; trigram indexes are documented
     for large tables that need search.
3. **Permissions** replace role checks. Done
   ([plan](plans/step-3-permissions.md)): apps declare permissions, roles are
   sets of them edited in Administration › Roles, every check names a
   permission. Binding scopes wait for bindings.
4. **Integration standards.** Done: [ADR 0011](adr/0011-integration-standards.md)
   (URN references, CloudEvents, published views, OpenAPI) and this order of
   work. What Taskline must provide was agreed with Taskline on 19 October
   ([ADR 0012](adr/0012-taskline-ui-and-contract.md), `docs/integrations/taskline.md`).
5. **Core components.** Done ([plan](plans/step-5-core-components.md)):
   saved grid views, personal and shared; charts with Chart.js and its plugins
   ([ADR 0004](adr/0004-charts-chartjs.md)); the record page component; forms
   from JSON Schema and the document store
   ([ADR 0007](adr/0007-json-schema-forms.md)); the stepper, the tree and the
   graph, whose trial passed ([ADR 0005](adr/0005-graphs-xyflow-web-component.md)).
6. **The showcase.** Done ([plan](plans/step-6-showcase.md)): the demo app
   is replaced by `apps/showcase`, one page per capability on sample data, each
   saying what it shows and what it is built with.
7. **Integration framework.** Done ([plan](plans/step-7-integration-framework.md)):
   URN references with resolvers, record panels and the CloudEvents bus
   ([ADR 0011](adr/0011-integration-standards.md)). An event-feed reader was
   built and then removed ([ADR 0012](adr/0012-taskline-ui-and-contract.md)).
8. **The showcase uses the framework.** Done: a second app, Comments, comments
   on any record by reference; the showcase resolves its events and claims, shows
   the Comments panel on their pages, and tells a claim's handler about new
   comments.
9. **Taskline UI** ([ADR 0012](adr/0012-taskline-ui-and-contract.md)):
   - Taskline builds its public contract: the `taskline_api` views and async
     commands, released as 0.2.0 (its plan steps 8 to 11);
   - in Lattice: async grid actions (done) and Postgres 18 (done);
   - Taskline UI in its own repository, `taskline-ui`: runs, run detail with the
     stepper, queues, workers, cancel and retry, run job, a Jobs panel on any
     record.
10. **Catastrophe response showcase.** Done ([plan](plans/step-10-cat-response-showcase.md),
    [ADR 0013](adr/0013-geoengine-and-maps.md)): the sample pages are replaced
    by one story a P&C audience knows; `geoengine` (PostGIS, H3, location
    quality) and the map component with draw-to-search.
11. **Incidents** in its own repository, after its own design document.

## 12. Open questions

| # | Question | Notes |
|---|---|---|
| O-1 | Where do business apps live: their own repositories (recommended) or `apps/` here? | Own repositories keep Lattice free of business code |
| O-2 | How are Lattice and its apps distributed to other repositories? | Decided: git tags for releases, editable path sources for development, a private package index once there are several consumers (section 3) |
| O-3 | Does the Ops console need its own sign-in, or does it use the same OIDC provider as the business hosts? | Affects how users and permissions are shared across hosts |
| O-4 | Who owns the reference kinds taskline already registers (`document`)? | Decided by ADR 0011: the owning app (`strategiq.document`); Taskline only stores the kind |
