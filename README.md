# Lattice

A platform for internal web applications. Sign-in, administration, navigation,
search and the UI components are done; applications plug in as separate packages,
and a host chooses which ones it runs. Built for agentic coding — the conventions
in [AGENTS.md](AGENTS.md) keep every screen consistent.

**Out of the box**

- Navigation shell: icon rail, section sidebar, breadcrumbs, status bar, all from one manifest
- **Ctrl+J** search: filter by source (pages, each grid's records, commands), with a preview pane
- Apps plug in through an `AppManifest`; a host is `create_app(apps=[…])`
- Branding per host: light/dark logos, a brand-token theme, page overrides and slots
- Password and **OIDC** sign-in (Entra ID, Okta, Keycloak, …), forced password change, pending-access gate
- Users, roles, sessions, audit log, system info, UI kit (Administration)
- User preferences: theme (light/dark/system), density, page size, start page, time format
- One **standard data grid**: search, filters, views, sort, paging, multi-select,
  bulk and row actions with confirm/input dialogs, side panel or reading pane,
  column chooser, CSV export, live refresh, keyboard control, URL state
- A demo app showing the grid in three shapes: Work Queue (submissions),
  Jobs (live job list), Inbox (email browsing)

**Stack**: Python 3.14, FastAPI, Jinja2, HTMX, Alpine.js, SQLAlchemy 2, Alembic, a uv
workspace. SQLite until the move to Postgres. No Node build.

## Run

```bash
cp .env.example .env     # optional; defaults work for development
make setup               # install the workspace, lattice migrate, lattice seed
make dev                 # lattice dev: http://localhost:8000
```

Sign in as `admin@example.com` / `Admin12345!` (also `editor@…`/`Editor12345!`,
`viewer@…`/`Viewer12345!`).

## Docs

- [AGENTS.md](AGENTS.md) — rules and recipes (read this first)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — where Lattice is going: kernel, components, apps, hosts
- [docs/adr/](docs/adr/README.md) — architecture decisions
- [docs/GRID.md](docs/GRID.md) — the grid contract
- [docs/UI_STANDARDS.md](docs/UI_STANDARDS.md) — page patterns and components
- [docs/AUTH.md](docs/AUTH.md) — sign-in, OIDC setup, roles, sessions

## Layout

```
lattice/                 the core package
  api.py                 the only module apps import
  kernel/                auth, nav, db, models, services, web, icons, slots, css_rules
  components/            grid/, search/ (Ctrl+J), tiles, manifest (AppManifest)
  platform/              home, account, admin: Lattice's own apps
  host.py                create_app and the app checks
  cli.py                 lattice migrate | create-user | seed | dev
  testing.py             pytest fixtures for core and app tests
  templates/  static/    shell layout, macros; five CSS layers, JS
apps/demo/               lattice-demo: the example app and its tests
hosts/demo/              lattice-demo-host: runs Lattice with the demo app
alembic/                 migrations
tests/                   core tests
```
