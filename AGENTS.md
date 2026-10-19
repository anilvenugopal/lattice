# Lattice — Agent Instructions

Lattice is a platform that web applications run on. The core package (`lattice`)
supplies sign-in, users, roles, navigation, Ctrl+J search, preferences, theme,
audit, and the UI components (the standard grid first). Applications are
separate packages that plug in through an `AppManifest`; a **host** chooses the
apps it runs. The design is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
This file is the single source of truth for coding agents. `CLAUDE.md` points here.

## Git

- **No AI attribution in git history**: never add `Co-Authored-By: Claude ...`,
  `Co-Authored-By: Codex ...`, or "Generated with ..." lines to commits or PR bodies.

## Stack

Python 3.14, FastAPI + Jinja2 + HTMX + Alpine.js, Postgres 17, a uv workspace.
**Plain SQL, no ORM:** every statement is a named query in a `sql/*.sql` file,
run through SQLAlchemy Core with the psycopg 3 driver. Server-rendered.
**No SPA, no npm build, no CSS framework.** Vendored JS lives in
`lattice/static/js/vendor/`. The one exception is the graph component: built
from `frontend/graph/` with `npm run build`, and its output file committed
(ADR 0005). Rebuild it only when changing that component; apps never run npm.

```bash
make db-up     # start Postgres (compose.yaml, port 5436); once per machine boot
make setup     # uv sync --all-packages, lattice migrate, lattice seed
make dev       # lattice dev: http://localhost:8000  (admin@example.com / Admin12345!)
make test      # core and app tests; always run before handing off
make lint      # ruff and the import contracts
make migrate   # apply new sql/schema/*.sql migrations
make reset     # drop Lattice's and the apps' schemas, migrate and seed (development)
```

Agents do not start, stop or rebuild containers: ask the user to run `make db-up`.

Always use `uv run …`; bare `python`/`pytest` miss the environment. Settings
are `LATTICE_*` environment variables (`.env.example`).

## Where things live

| Path | Owns |
|---|---|
| `lattice/api.py` | **The only module apps import.** Changing or removing a name is a breaking change |
| `lattice/kernel/` | No UI components: config, `database.py` (shared engine, `Db`, `get_db`, `transaction`), `sql.py` (named-query loader), `migrate.py`, `queries.py`, `auth/`, `nav/`, `services/` (audit, users, preferences), `web.py` (render, flash, toast, filters), `icons.py`, `slots.py`, `css_rules.py` |
| `lattice/sql/` | Lattice's named queries (one file per area) and `schema/` migrations for schema `lattice` |
| `lattice/components/` | `grid/` (spec, engine, render, router), `search/` (Ctrl+J providers and routes), `tiles.py` (home tiles), `manifest.py` (`AppManifest`) |
| `lattice/platform/` | Lattice's own apps, built with `AppManifest`: `home.py`, `account.py`, `admin.py` |
| `lattice/host.py` | `create_app(apps=[…])`: registers apps and checks they stay in their namespace |
| `lattice/cli.py` | `lattice migrate`, `new-migration`, `reset`, `create-user`, `seed`, `dev`, `docs build\|check` |
| `lattice/testing.py` | Pytest fixtures for core and app tests (`db`, `users`, `client`, `as_user`, `host_apps`…) |
| `lattice/templates/`, `lattice/static/` | Shell layout, shared macros, grid templates; the five CSS layers |
| `apps/showcase/` | `lattice-showcase`: every component on sample data (Items, Live updates, Reading pane, Charts, Specs, Free-form, Flows), its `sql/` (schema `showcase` and named queries), templates, styles, seed and tests |
| `hosts/showcase/` | `lattice-showcase-host`: runs Lattice with the showcase app |
| `tests/sql/`, `apps/*/tests/sql/` | Named queries the tests use to set up and check rows |
| `compose.yaml` | Postgres 17 for development and tests |
| `docs/ARCHITECTURE.md`, `docs/adr/` | Target design and decisions. Read before changing anything they cover |
| `lattice/help/` | The user guide and developer guide, served in the app at `/help`. `developer/building-apps/` covers the grid, pages, styling and access; `developer/running/` covers sign-in, users and branding. `developer/reference/` is generated: run `uv run lattice docs build` after changing what it documents |

Layers (checked by `tests/test_import_contracts.py`): `kernel` ← `components` ←
`platform` ← `host` ← `api` ← `testing`, `reference` ← `cli`. Each imports only
the layers below it. Apps import only `lattice.api`.

## Rules

### UI consistency (enforced in review)

1. **Every list of records is a `GridSpec`.** Do not write a `<table>` for records,
   a custom pager, a custom filter bar, custom bulk-selection JS, or a bespoke
   side panel. If the grid cannot do something, extend `lattice/components/grid/`
   for everyone and update `lattice/help/developer/building-apps/grids.md`. Plain `.table` is only for short fixed
   lists inside a card (≤ ~10 rows, no selection, e.g. a user's sessions).
2. **Every page goes through `render_page(request, template, nav_key, **ctx)`**
   (partials: `render(request, template, **ctx)`; both take context as keyword
   arguments) and every page has a `NavNode` in its app's manifest. Detail pages
   use a `hidden=True` node whose parent is the list node, and pass
   `crumb=<record name>`.
3. **Use the macros in `components/macros.html`** and icons via `{{ icon("name") }}`
   (core set in `lattice/kernel/icons.py`; an app's own icons are
   `icon("{key}:name")`). The macros cover these areas:
   - **Layout:** `page_header`, `card`, `stat`, `prop_list`, `empty_state`, `timeline`.
   - **Status:** `badge`, `badge_for`, `alert`, `progress`, `user_chip`.
   - **Forms:** `field`, `select_field`, `checkbox`, `pref_row`, `segmented`, `select_input`.
   - **Shell:** `brand`, `signout_button`, `session_table`.

   Add a new macro there, and to the UI kit page, rather than inline markup in an app.
   Import macros that use `csrf_field()` `with context`.
4. **CSS follows the five layers** — settings → base → layout → components →
   utilities — declared with `@layer` in `lattice/static/css/app.css`.
   `tests/test_css_architecture.py` enforces these rules for core CSS:
   - colour literals and `--p-*` tokens appear only in `1-settings/tokens.css`;
   - `2-base` has no class selectors;
   - `5-utilities` holds only `.u-*` classes, and is the only place `!important` is allowed;
   - every file is imported into the layer matching its folder.

   Components use semantic tokens (`var(--text-2)`, `var(--sp-3)`). Tones are the
   modifier classes `tone-neutral|info|success|warning|danger|accent` on `badge`,
   `tag`, `alert` and `code-block`.

   **An app's styles** live in its own stylesheet (`AppManifest.stylesheets`). It
   declares `@layer components`, every selector starts with `[data-app="{key}"]`,
   and it has no colour literals, `--p-*` tokens or `!important`. **A host theme**
   (`static/theme.css` in the host folder) may set only the brand tokens, in both
   light and dark. `create_app` refuses to start on a violation
   ([ADR 0010](docs/adr/0010-theming-and-overrides.md)). Templates carry no inline
   colours or styles beyond computed widths.
5. **Status values render through their grid Column.** Declare labels and tones once,
   on the `Column`. Templates call `badge_for(spec.column("status"), value)`,
   `label_for(...)` and `tone_for(...)`. Do not pass tone maps to templates.
6. **Timestamps** are naive UTC in the database and render with `time_tag(value)`;
   the browser localises them and honours the user's time format preference.
7. **Feedback** after an action is a toast. Choose by route type:
   - grid action handler: return a message;
   - HTMX route: `headers=toast("…")`;
   - full-page form that redirects: `flash(response, request, "…")`, which shows the toast on the next page load.

   No `alert()` and no `?saved=1` banners.
8. **Forms**: full-page forms post with `{{ csrf_field() }}` and redirect (303) on
   success; on validation failure re-render with `errors` per field and status 400.
   In-place forms use `hx-post`; the CSRF header is added automatically.

### Apps

- An app is a package with one `AppManifest` (exported as `APP`). It imports only
  `lattice.api`, and never another app.
- Everything an app adds is in its namespace, or `create_app` refuses to start:
  - routes are mounted under `/{key}`, and nav routes and grid paths start with it;
  - grid keys start with `{key}.`;
  - templates live in `templates/{key}/`, static files in `static/` (served at
    `/static/{key}/`), icons as `{key}:name`, slot templates in `{key}/`.
- **Across apps** (ADR 0011): refer to another app's record by URN
  (`urn:lattice:{kind}:{id}`, drawn with `{{ ref(urn) }}`), never by foreign key;
  declare `references=` (kinds and resolvers), `panels=` (RecordPanels on other
  apps' record pages), `publishes=` and `subscribes=` (CloudEvents, delivered after
  commit) and `feeds=` (outboxes). Guide:
  `lattice/help/developer/building-apps/working-across-apps.md`.
- Background work: `background=` (an async function started with the host).
  Example data: `seed=` (run by `lattice seed`).

### Security

- Every router that changes data has `Depends(csrf_protect)` in its `dependencies=[…]`.
- **Permissions, never role names.** An app declares its permissions in its
  manifest (`Permission("{key}.area.verb", label, description, default_roles=…)`).
  Checks name one permission: `require("…")` on routes, `permission="…"` on
  `NavNode`, `GridSpec`, `Action` and `SearchProvider`, `permission:` in help
  front matter, `current_user.can("…")` in templates. Administrators group
  permissions into roles in Administration › Roles; the admin role has every
  permission. Hiding a button is not access control; the server checks all of
  them. `create_app` refuses an undeclared permission.
- A grid's `query` is its access boundary. Rows a user may not see must be filtered
  in that named query (see `apps/showcase/lattice_showcase/sql/inbox.sql`:
  `WHERE m.owner_id = :user_id`). Actions, panels, export and Ctrl+J results all
  go through it. A detail route loading a record by id applies the same condition.
- Never log or render passwords, session tokens or OIDC tokens. Session ids in
  the database are SHA-256 hashes of the cookie.

### Data

- **Plain SQL, no ORM.** Every SQL statement is a named query in `sql/<area>.sql`
  (`-- name: x` then a `--` comment line), loaded with
  `sql_queries(Path(__file__).parent / "sql").<area>` and run through `Db`:
  `db.all`, `db.first`, `db.one` (404 when missing), `db.value`, `db.run`.
  Values are `:placeholders`; a list becomes an array (`= ANY(:ids)`); cast with
  `CAST(:x AS type)`, never `:x::type`. Never write SQL in Python, never import
  `sqlalchemy.orm`; apps never import SQLAlchemy or psycopg.
- Routes take `db: Db = Depends(get_db)`. Each request is one transaction, saved
  when the route returns: routes and grid handlers never commit. Outside a
  request, use `with transaction() as db:`.
- Grid writes are audited per row automatically. Other writes call
  `audit.record(...)` in the same request.
- Schema changes: `make migration schema=<key> m="what changes"`, write the SQL,
  `make migrate`. Tables live in the schema named after the app's key; timestamps
  are `timestamp DEFAULT lattice.utc_now()`. Never edit a migration that has been
  merged. Seed lookup rows (roles, kinds) in the migration that creates their table.
- `tests/test_sql_rules.py` fails on an unused named query, a missing one, one
  Postgres rejects, or SQL written in Python. Delete queries nobody uses.
- Apps refer to each other's records by reference, never by foreign key
  ([ADR 0001](docs/adr/0001-postgres-with-per-app-bindings.md)).

### Code quality

Implement the smallest change that satisfies the requirement.

- Do not add behaviour for hypothetical scale or future requirements.
- Do not add an abstraction for one caller unless it makes the caller simpler.
- Comments explain constraints that names and structure cannot. Do not narrate code.
- Before handoff, review the diff for subtraction: remove comments that restate
  code, helpers that only rename a call, speculative options.
- Tests: add or update tests for every route, action and permission you add — core
  tests in `tests/`, an app's tests in its own `tests/` with `host_apps` set to the
  app. `make test` must pass (Postgres running). Report the count, e.g. "227 passed".

## Recipes

### Add a list page (the common case)

Follow `.claude/skills/add-grid-page/SKILL.md`. In short, in the app's package:

1. The table in a migration (`make migration schema=<app> m="add <table>"`), and
   the named queries in `sql/<area>.sql`: `grid`, and one per action.
2. A module with `SQL = sql_queries(...).<area>`, the `GridSpec` (key `{app}.name`,
   path `/{app}/…`, `query=SQL.grid`), action handlers running `ctx.db.run(...)`,
   and a `router` whose page route calls `render_grid_page(...)`.
3. In the app's `AppManifest`: add the router to `routers=`, the grid to `grids=`,
   its `NavNode`s to `nav=`, and optionally `HomeTile`s to `tiles=`.
4. Tests in the app's `tests/`: page renders, an action works, a role that must not
   run it gets 403.

### Add an app

Follow the tutorial in `lattice/help/developer/getting-started/first-app.md`:
a package exporting `APP = AppManifest(key="<name>", …, sql=HERE / "sql")`,
`sql/schema/0001_<name>.sql`, named queries, and `tests/conftest.py` setting
`host_apps`. Add it to a host's `create_app(apps=[…])`, the root dev dependencies,
`testpaths`, ruff's `known-first-party` and the import contracts in
`pyproject.toml`. Copy `apps/showcase` for the shape.

### Add a detail page

Declare a `RecordPage` on the list's grid and render it with
`render_record_page(request, db, PAGE, id)`, as in
`apps/showcase/lattice_showcase/items.py` (`DETAIL`). It reads the row through
the grid's query, shows the grid's row actions, properties, panels and the
audit history. Guide: `lattice/help/developer/building-apps/record-pages.md`.

### Add a permission or a role

- **A permission** is code: add a `Permission` to the app's `permissions=`, use
  it in `require(...)`/`permission=`, run `make migrate` (it records the
  permission and grants its `default_roles` once), and test both a user who has
  it and one who does not.
- **A role** is data: administrators create it in Administration › Roles and
  tick its permissions. No code or migration.

### Add a preference

Add the key to `DEFAULTS` and `CHOICES` in `lattice/kernel/services/preferences.py`,
a row in `templates/account/preferences.html`, and read it with
`preferences.get(user, key)` (`prefs.get(current_user, key)` in templates).

### Ctrl+J search

- **Pages** are searchable through their `NavNode` (label, keywords, description).
- **Records** are searchable when their GridSpec sets `palette=Palette(title, href, subtitle, icon)`. The preview pane shows that grid's side panel, read-only.
- **Commands:** add a `(key, label, description)` row to `COMMANDS` in `lattice/components/search/providers.py`, and a branch for the key in `runCommand()` in `lattice/static/js/palette.js`.
- **Another source** (an external system): a `SearchProvider` in the app's manifest `search=`.

### Branding and host customisation

- Name and logos: `LATTICE_APP_NAME`, `LATTICE_BRAND_LOGO_LIGHT`,
  `LATTICE_BRAND_LOGO_DARK`, `LATTICE_BRAND_SHOW_NAME`.
- Colours and fonts: `static/theme.css` in the host folder (`create_app(host_dir=…)`),
  brand tokens only.
- Whole pages: `templates/auth/login.html`, `templates/base/error.html` or
  `templates/pages/home.html` in the host folder.
- Small additions: slots (`topbar.end`, `statusbar.start`, `statusbar.end`,
  `signin.footer`, `home.sections`, `help.menu`) through `slot_templates=` or an
  app's `slots=`.
- Icon set: `create_app(icons_override={…})`.

## The showcase app

`apps/showcase` shows every component on sample data, one module per page:
`items.py` (table grid, record page, plain forms), `jobs.py` (polling grid with
state-dependent actions), `inbox.py` (split list and reading pane), `charts.py`,
`specs.py` (forms from JSON Schema, the document store, an inferred form) and
`flows.py`. Its data means nothing; a real host replaces it with its own apps.

## Writing style

Name the real thing (the table, route, column, action). No filler words
(`robust`, `leverage`, `seamless`, `comprehensive`). Lead with the answer.
Commit subject ≤ 72 characters; the body says why.
