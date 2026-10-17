# Lattice — Agent Instructions

This repo is a template for internal web applications. It supplies the shell
(navigation, Ctrl+J search, sign-in, users, roles, preferences, theme, audit) and
one standard data grid. Applications built from it add **feature modules**.
This file is the single source of truth for coding agents. `CLAUDE.md` points here.

## Git

- **No AI attribution in git history**: never add `Co-Authored-By: Claude ...`,
  `Co-Authored-By: Codex ...`, or "Generated with ..." lines to commits or PR bodies.

## Stack

FastAPI + Jinja2 + HTMX + Alpine.js, SQLAlchemy 2.0, Alembic, SQLite by default
(any SQLAlchemy URL in `DATABASE_URL`). Server-rendered. **No SPA, no npm build,
no CSS framework.** Vendored JS lives in `app/static/js/vendor/`.

```bash
make setup     # uv sync + migrate + seed
make dev       # http://localhost:8000  (admin@example.com / Admin12345!)
make test      # always run before handing off
make lint
```

Always use `uv run …`; bare `python`/`pytest` miss the environment.

## Where things live

| Path | Owns |
|---|---|
| `app/nav/manifest.py` | All navigation: rail, sidebar, breadcrumbs, role gating of menus, Ctrl+J page results |
| `app/grid/` | The standard grid: `spec.py` (declaration), `engine.py` (SQL), `router.py` (endpoints), `render.py` |
| `app/features/<area>.py` | One feature area: its GridSpecs, routes, handlers |
| `app/templates/features/` | Templates owned by feature modules |
| `app/templates/components/` | Shared macros (`macros.html`) and grid templates. Do not fork per feature |
| `app/static/css/` | Five ITCSS layers (see `app.css` and `docs/UI_STANDARDS.md`); tokens in `1-settings/tokens.css` |
| `app/routers/` | Platform routes: auth, account, admin, shell (home, Ctrl+J search, health) |
| `app/search.py` | Ctrl+J search providers: pages, one per grid with `palette=`, commands, `register_provider()` |
| `app/services/` | `audit` (record, history), `users` (lookup, create), `preferences`, `home` (home tiles) |
| `app/auth/roles.py` | Role codes (`ADMIN`, `ADMINS`, `EDITORS`). Never write role strings elsewhere |
| `app/models.py` + `alembic/versions/` | Schema. Every model change ships with a migration |
| `docs/ARCHITECTURE.md` | Target design: kernel, components, apps, hosts, and the order of work |
| `docs/adr/` | Architecture decisions, one file each. Read before changing anything they cover |
| `docs/GRID.md` | Grid contract and recipes |
| `docs/UI_STANDARDS.md` | Page patterns, components, styling rules |
| `docs/AUTH.md` | Password and OIDC sign-in, roles, sessions |

## Rules

### UI consistency (enforced in review)

1. **Every list of records is a `GridSpec`.** Do not write a `<table>` for records,
   a custom pager, a custom filter bar, custom bulk-selection JS, or a bespoke
   side panel. If the grid cannot do something, extend `app/grid/` for everyone and
   update `docs/GRID.md`. Plain `.table` is only for short fixed lists inside a
   card (≤ ~10 rows, no selection, e.g. a user's sessions).
2. **Every page goes through `render_page(request, template, nav_key, **ctx)`** (partials:
   `render(request, template, **ctx)`; both take context as keyword arguments) and
   every page has a `NavNode`. Detail pages use a `hidden=True` node whose parent is
   the list node, and pass `crumb=<record name>`.
3. **Use the macros in `components/macros.html`** and icons via `{{ icon("name") }}`
   (`app/icons.py`). The macros cover these areas:
   - **Layout:** `page_header`, `card`, `stat`, `prop_list`, `empty_state`, `timeline`.
   - **Status:** `badge`, `badge_for`, `alert`, `progress`, `user_chip`.
   - **Forms:** `field`, `select_field`, `checkbox`, `pref_row`, `segmented`, `select_input`.
   - **Shell:** `brand`, `signout_button`, `session_table`.

   Add a new macro there, and to the UI kit page, rather than inline markup in a feature.
   Import macros that use `csrf_field()` `with context`.
4. **CSS follows the five layers** — settings → base → layout → components →
   utilities — declared with `@layer` in `app/static/css/app.css`.
   `tests/test_css_architecture.py` enforces these rules:
   - colour literals and primitive tokens (`--p-*`) appear only in `1-settings/tokens.css`;
   - `2-base` has no class selectors;
   - `5-utilities` holds only `.u-*` classes, and is the only place `!important` is allowed;
   - every file is imported into the layer matching its folder.

   Components use semantic tokens (`var(--text-2)`, `var(--sp-3)`). Tones are the
   modifier classes `tone-neutral|info|success|warning|danger|accent` on `badge`,
   `tag`, `alert` and `code-block`. A new colour is a primitive, then a semantic
   token defined in both the light and the dark block. Feature-owned styles go in
   their own section of `4-components/features.css`. Templates carry no inline
   colours or styles beyond computed widths.
5. **Status values render through their grid Column.** Declare labels and tones once,
   on the `Column`. Templates call `badge_for(spec.column("status"), value)`,
   `label_for(...)` and `tone_for(...)`. Do not pass tone maps to templates.
6. **Timestamps** are naive UTC in the database and render with `time_tag(value)`;
   the browser localises them and honours the user's time format preference.
7. **Feedback** after an action is a toast. Choose by route type:
   - grid action handler: return a message;
   - HTMX route: `headers=toast("…")`;
   - full-page form that redirects: `flash(response, request, "…")` (from `app.web`), which shows the toast on the next page load.

   No `alert()` and no `?saved=1` banners.
8. **Forms**: full-page forms post with `{{ csrf_field() }}` and redirect (303) on
   success; on validation failure re-render with `errors` per field. In-place forms
   use `hx-post`; the CSRF header is added automatically.

### Security

- Every route that changes data includes `Depends(csrf_protect)` (routers set it
  once via `dependencies=[…]`).
- Role checks: `require_roles(...)` on routes, `roles=` on `NavNode`, `GridSpec`
  and `Action`. Hiding a button is not access control; the server checks all three.
- A grid's `query` is its access boundary. Rows a user may not see must be filtered
  in `query` (see `inbox.py`: `where(Message.owner_id == user.id)`). Actions,
  panels, export and palette results all go through it.
- Never log or render passwords, session tokens or OIDC tokens. Session ids in
  the database are SHA-256 hashes of the cookie.

### Data

- All access through SQLAlchemy sessions (`Depends(get_db)`); bind parameters only.
- Grid action handlers do not commit; the grid writes one audit event per row and commits.
- Other writes call `audit.record(...)` then `db.commit()` in the route.
- Schema changes: edit `app/models.py`, then `make revision m="what changes"`,
  read the generated file, fix anything autogenerate got wrong, `make migrate`.
  Never edit a migration that has been merged. Seed lookup rows (roles, kinds) in
  the migration that creates their table.
- Keep queries portable: SQLite in development, Postgres or SQL Server in production.
  Avoid dialect-specific functions unless guarded (see `users_query` in `admin.py`).

### Code quality

Implement the smallest change that satisfies the requirement.

- Do not add behaviour for hypothetical scale or future requirements.
- Do not add an abstraction for one caller unless it makes the caller simpler.
- Comments explain constraints that names and structure cannot. Do not narrate code.
- Before handoff, review the diff for subtraction: remove comments that restate
  code, helpers that only rename a call, speculative options.
- Tests: add or update tests in `tests/` for every route, action and permission
  you add. `make test` must pass. Report the count: "57 passed".

## Recipes

### Add a list page (the common case)

Follow `.claude/skills/add-grid-page/SKILL.md`. In short:

1. Model + migration (if the table is new).
2. `app/features/<area>.py`: `query()`, `GridSpec(...)` registered with `register()`,
   action handlers, `router` with the page route calling `render_grid_page(...)`.
3. `NavNode`s in `app/nav/manifest.py`.
4. Add the module to `FEATURES` in `app/main.py`. That includes its `router`, and starts
   its optional `async def background()` at startup.
   Optional: `register_tile(HomeTile(...))` for a count on the home page (`app/services/home.py`).
5. Tests: page renders, an action works, a role that must not run it gets 403.

### Add a detail page

Copy the pattern in `work_items.py` (`detail`, `edit_form`, `save`) and
`templates/features/work_item_detail.html`: `page_header` with status badge and
actions, `prop_list` in a card, `timeline(history(...))` for activity.

### Add a role

Add it in a migration (`op.bulk_insert` into `role`), then reference the code in
`roles=` on nav nodes, grids and actions. Admins assign roles in Administration › Users.

### Add a preference

Add the key to `DEFAULTS` and `CHOICES` in `app/services/preferences.py`, a row in
`templates/account/preferences.html`, and read it with `preferences.get(user, key)`
(`prefs.get(current_user, key)` in templates).

### Ctrl+J search

- **Pages** are searchable through their `NavNode` (label, keywords, description).
- **Records** are searchable when their GridSpec sets `palette=Palette(title, href, subtitle, icon)`. The preview pane shows that grid's side panel, read-only.
- **Commands:** add a `(key, label, description)` row to `COMMANDS` in `app/search.py`, and a branch for the key in `runCommand()` in `app/static/js/palette.js`.
- **Another source** (an external system): `register_provider(SearchProvider(...))` in `app/search.py`.

### Branding

Set `APP_NAME`, `BRAND_LOGO_LIGHT`, `BRAND_LOGO_DARK` and `BRAND_SHOW_NAME` in `.env`,
and put the logo files in `app/static/brand/`. The `brand()` macro shows the variant
that matches the theme. The favicon follows the operating-system theme.

## Example features

`work_items.py`, `jobs.py` and `inbox.py` exist to show the patterns: a table grid
with views, bulk actions and a detail page; a polling grid with state-dependent
actions; a split list + reading pane. Replace them with your domain. Delete a
feature by removing its module, its entry in `FEATURES` in `app/main.py`, its nav nodes,
templates and tests, and its tables in a new migration.

## Writing style

Name the real thing (the table, route, column, action). No filler words
(`robust`, `leverage`, `seamless`, `comprehensive`). Lead with the answer.
Commit subject ≤ 72 characters; the body says why.
