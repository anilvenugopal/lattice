# Step 5 plan: core components

Status: **done** on the `step-5` branch (18 October 2026). You asked me to
proceed without stopping for approval until Taskline is needed, so the
decisions below are mine. Each names the alternative, so any of them can be
reversed at review. How the result differs from the plan is at the end.

## What step 5 delivers

Five components every app can place on its pages, each following the grid's
pattern: a Python spec, shared endpoints keyed by the spec, a Jinja macro, an
Alpine component and one CSS file.

| # | Component | What a user gets |
|---|---|---|
| 1 | **Saved grid views** | Save the grid's filters, search and sort under a name; reopen it from the Views menu; share it with everyone |
| 2 | **Charts** | Bar, line, area, pie, calendar heatmap, treemap, sankey and map charts on any grid's rows, following the grid's filters on the same page |
| 3 | **Record page** | A standard detail page from a spec: header with status and actions, properties, the app's panels and history |
| 4 | **Forms from JSON Schema** and the **document store** | Any JSON document as an editable form, validated on the server; a table for documents of mixed shape |
| 5 | **Flows** | A stepper for linear flows, a collapsible tree for hierarchies, and a graph for DAGs |

## Stages

On a branch, `step-5`, one commit per stage. Every stage ends with `make test`
and `make lint` passing, and its help pages written.

### 1. Saved grid views

```text
Views ▾   ─────────────────────────
          Mine
            Overdue marine         ✎ 🗑
          Shared
            Q4 renewals
          ─────────────────────────
          Save current view…
```

- **What is saved:** the grid's URL state (built-in view tab, search, filters,
  sort, page size), not the page number. Columns stay a per-user preference.
- **Storage:** `lattice.grid_view` (id, grid key, owner, name, the state as a
  query string, shared, timestamps). Named queries in `lattice/sql/grid_views.sql`.
- **Endpoints:** `GET/POST /_grid/{key}/views`, `POST /_grid/{key}/views/{id}`
  (rename, update, share), `POST …/delete`.
- **Who:** anyone who can open the grid saves their own views. Sharing needs the
  new permission `lattice.views.share` (default: editor). Owners and holders of
  `lattice.views.share` delete shared views.
- **Opening one** puts its state in the URL, so a saved view is also a link.

Decision 1: views are **personal, optionally shared with everyone** (not per
role or per team; that waits for teams).

### 2. Charts ([ADR 0004](../adr/0004-charts-chartjs.md))

```python
RUNS_BY_DAY = ChartSpec(
    key="demo.work_by_day", title="Created per day", source=WORK_GRID, kind="bar",
    x=Time("created_at", unit="day"), y=Count(), series="status")
```

- **Aggregation in the database:** the chart wraps its grid's filtered query in
  `SELECT x, series, agg(...) … GROUP BY`. The access boundary is the grid's
  query, as for every other read.
- **Linked to a grid on the same page:** when the grid's filters, search or view
  change, the chart reloads with the same state. A chart on its own uses the
  grid's defaults and can be fixed like an embedded grid (`fixed=`).
- **Kinds:** `bar`, `line`, `area`, `pie`, `doughnut`, `calendar` (matrix),
  `treemap`, `sankey`, `choropleth` (geo, world countries). Thresholds as
  annotation lines; zoom and pan on time axes.
- **Measures:** `Count()`, `Sum(col)`, `Avg(col)`, `Min(col)`, `Max(col)`.
  **Dimensions:** a column, or `Time(col, unit)` with `date_trunc`.
- **Colours from the CSS tokens:** a series on a status column takes that
  column's tones; other series take a fixed token palette. Both follow dark mode.
- **Libraries vendored** in `static/js/vendor/chart/`, exact versions recorded
  in a `VERSIONS` file, loaded only on pages that place a chart.
- **Endpoint:** `GET /_chart/{key}/data?<grid state>` returns the series as JSON.

Decision 2: a chart's source is **a GridSpec** (its query, filters and access
boundary), not a separate chart query. A chart with no visible grid declares a
GridSpec it never places.

### 3. Record page

```python
WORK_ITEM_PAGE = RecordPage(
    grid=WORK_GRID, nav_key="work.detail", title="{ref} · {title}", status="status",
    properties=["owner", "priority", "due_on", "amount"],
    panels=[Panel("notes", "Notes", template="demo/work_item_notes.html")],
    history=True)

@router.get("/work/{item_id}")
def detail(item_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, WORK_ITEM_PAGE, item_id)
```

- **Loads the row through the grid's query**, so a record page shows nothing
  its list would not.
- **Header:** title, status badge from the grid's Column, and the grid's
  single-row actions that apply to this row, run through the grid's action
  endpoint (same confirm dialogs, permissions and audit).
- **Properties** render with their grid Column kinds (money, date, user, badge…).
- **Panels:** the app's own, in order. Step 7 adds panels from other apps.
- **History:** the audit timeline for the record.

Decision 3: the record page is **built on the grid** (row, columns, actions),
not a separate record model.

### 4. Forms from JSON Schema, and the document store ([ADR 0007](../adr/0007-json-schema-forms.md))

```python
form = build_form(schema=Settings.model_json_schema(), data=current, ui={...})
# template: {{ json_form(form) }}
data, errors = parse_form(form_data, schema)
```

- **Rendered on the server** by recursive macros: object (fieldsets), array (add,
  remove, reorder rows), string (with `date`, `date-time`, `email`, `uri`,
  `textarea`), number, integer, boolean, enum, `$ref`/`$defs`, `oneOf` with a
  discriminator.
- **Round trip:** fields the schema doesn't describe appear under **Other
  fields** and come back unchanged. A **JSON** tab edits the raw document.
- **Validation** with `jsonschema` (Draft 2020-12) on the server; each error is
  shown at its field.
- **Schema resolution:** an explicit schema, then the document's `$schema`, then
  the document kind's registered schema, then one inferred from the document.
- **Document store:** `lattice.document` (id, kind, schema version, JSONB data,
  created and updated by and at), a `documents` service (get, list, create,
  update, delete, each audited), and document kinds declared in the manifest:
  `DocumentKind("demo.policy_template", "Policy template", schema=…, ui=…)`.

Decision 4: **one new dependency, `jsonschema`**, for validation. Inference and
rendering are Lattice code.

### 5. Flows ([ADR 0005](../adr/0005-graphs-xyflow-web-component.md))

- **Stepper** (macro): steps with a label, status tone, note and link,
  horizontal or vertical.
- **Tree** (macro): nested nodes with status, link and collapse.
- **Graph** (`<lt-graph>`): Svelte Flow with dagre layout, built once in
  `frontend/graph/` with Vite. The built file is committed to
  `static/js/vendor/`, so app authors never run npm. Nodes link to records, and
  node actions run through a grid's action endpoint.
- **The spike criteria come first:** htmx swaps, dark mode from tokens, a
  200-node DAG, keyboard focus, and the file size. If Svelte Flow fails them,
  React Flow is the fallback (ADR 0005).

### 6. Docs and the UI kit

Help pages for each component under **Building apps**, the UI kit page showing
each, the reference pages regenerated, ARCHITECTURE section 6 and the Decisions
page updated. ADR 0007 and 0005 move to Accepted when their stage passes.

## Not in step 5

- **Grid data sources and keyset paging** (ADR 0008): step 9, with Taskline.
- **Panels from other apps** on the record page: step 7.
- **The form builder:** when two apps need it (ADR 0007).
- **Dashboards** as a saved arrangement of charts: the showcase (step 6) shows
  charts on pages; a dashboard builder waits for a need.

## How the result differs from the plan

| Area | Plan | Result, and why |
|---|---|---|
| Saved views | Edit and delete in the menu | As planned, plus **Save changes to "…"** when the user changes an open view of their own. Deleting asks in a dialog, not the browser's `confirm()` |
| Charts | `tones_from=` to colour series | Not needed: a series or category on a status column takes that column's tones automatically |
| Charts | — | Category charts keep the 12 largest values; with counts and sums the rest add up to a grey **Other** |
| Record page | Header, properties, panels, history | Also `Link`s (such as **Edit**) in the header, and panels placed `main`, `side` or `full` width. The demo's work item page uses it |
| Forms | Arrays edited in the browser | Every edit that changes the form's shape (add, remove, move, choose a variant, add a field, switch tabs, apply a schema) posts to `/_form/{key}/render` and redraws on the server: no form JavaScript, one place for the rules |
| Forms | `FormSpec(schema, ui, load, save)` | `FormSpec(key, schema, ui)`; the app's route loads and saves, as for every other form |
| Document store | In the kernel | In `components/documents.py` (it uses the form validation); storage is the `lattice.document` table and named queries |
| Grid | — | **New: `GridSpec.params`**, fixed values bound into the grid's query. The document store needs one query for many kinds |
| Graph | Node actions from the grid | Only actions without input fields: those with fields stay in the grid's dialogs |
| Graph | — | Library builds keep whitespace and leave `process.env`; the build config fixes both. 327 KB (100 KB compressed) |
| Rules | "No npm build" | Now "except the graph component, built once and committed" (AGENTS.md) |
| Dependencies | — | `jsonschema` 4.26 (with `referencing` and `rpds-py`) for validation |
| Docs | — | The "Not built yet" help page is gone: everything on it exists. New pages: Charts, Record pages, Forms from JSON Schema, Flows |
