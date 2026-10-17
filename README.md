# UI Shell

A starting point for internal web applications: the shell, sign-in and
administration are done; you add feature modules. Built for agentic coding — the
conventions in [AGENTS.md](AGENTS.md) keep every screen consistent.

**Out of the box**

- Navigation shell: icon rail, section sidebar, breadcrumbs, status bar, all from one manifest
- **Ctrl+J** search: filter by source (pages, each grid's records, commands), with a preview pane
- Swappable light/dark logo (`BRAND_LOGO_LIGHT`, `BRAND_LOGO_DARK`)
- Password and **OIDC** sign-in (Entra ID, Okta, Keycloak, …), forced password change, pending-access gate
- Users, roles, sessions, audit log, system info, UI kit (Administration)
- User preferences: theme (light/dark/system), density, page size, start page, time format
- One **standard data grid**: search, filters, views, sort, paging, multi-select,
  bulk and row actions with confirm/input dialogs, side panel or reading pane,
  column chooser, CSV export, live refresh, keyboard control, URL state
- Example features showing the grid in three shapes: Work Queue (submissions),
  Jobs (live job list), Inbox (email browsing)

**Stack**: FastAPI, Jinja2, HTMX, Alpine.js, SQLAlchemy 2, Alembic, SQLite by default.
No Node build.

## Run

```bash
cp .env.example .env     # optional; defaults work for development
make setup               # install, migrate, seed
make dev                 # http://localhost:8000
```

Sign in as `admin@example.com` / `Admin12345!` (also `editor@…`/`Editor12345!`,
`viewer@…`/`Viewer12345!`).

## Docs

- [AGENTS.md](AGENTS.md) — rules and recipes (read this first)
- [docs/GRID.md](docs/GRID.md) — the grid contract
- [docs/UI_STANDARDS.md](docs/UI_STANDARDS.md) — page patterns and components
- [docs/AUTH.md](docs/AUTH.md) — sign-in, OIDC setup, roles, sessions

## Layout

```
app/
  main.py            app, middleware, routers
  nav/manifest.py    navigation
  grid/              standard grid (spec, engine, router, render)
  features/          your feature modules (examples: work_items, jobs, inbox)
  routers/           auth, account, admin, shell
  auth/              sessions, passwords, OIDC, CSRF, middleware
  templates/         base/, components/, features/, admin/, account/, auth/
  static/            css/ (five ITCSS layers, app.css), js/ (app.js, grid.js, vendor/)
alembic/             migrations
scripts/             seed.py, create_user.py
tests/
```
