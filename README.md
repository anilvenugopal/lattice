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
- Charts, record pages, forms from JSON Schema with a document store, and
  flows (stepper, tree, graph)
- A showcase app with every component on sample data, one page per capability

**Stack**: Python 3.14, FastAPI, Jinja2, HTMX, Alpine.js, Postgres 18, a uv
workspace. Plain SQL in named `.sql` files, run through SQLAlchemy Core and
psycopg 3; no ORM. No Node build for apps (the graph component is built once and committed).

## Run

```bash
cp .env.example .env     # optional; defaults work for development
make db-up               # start Postgres 18 (compose.yaml, port 5436, podman-compose)
make setup               # install the workspace, lattice migrate, lattice seed
make dev                 # lattice dev: http://localhost:8000
```

Sign in as `admin@example.com` / `Admin12345!` (also `editor@…`/`Editor12345!`,
`viewer@…`/`Viewer12345!`).

## Docs

- [AGENTS.md](AGENTS.md) — rules and recipes (read this first)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — where Lattice is going: kernel, components, apps, hosts
- [docs/adr/](docs/adr/README.md) — architecture decisions
- **In the app:** press F1 or open `/help`. The developer guide (overview,
  getting started, architecture, building apps, running Lattice, reference) is
  in [lattice/help/developer/](lattice/help/developer/index.md), the user guide in
  [lattice/help/user-guide/](lattice/help/user-guide/index.md)

## Layout

```
lattice/                 the core package
  api.py                 the only module apps import
  kernel/                database (engine, Db), sql loader, migrations, auth, nav, services, web
  sql/                   Lattice's named queries; schema/ holds its migrations
  components/            grid/, search/ (Ctrl+J), tiles, manifest (AppManifest)
  platform/              home, account, admin: Lattice's own apps
  host.py                create_app and the app checks
  cli.py                 lattice migrate | new-migration | reset | create-user | seed | dev | docs
  testing.py             pytest fixtures for core and app tests
  help/                  the user guide and developer guide, served at /help
  templates/  static/    shell layout, macros; five CSS layers, JS
apps/showcase/           lattice-showcase: every component on sample data, its sql/ and tests
hosts/showcase/          lattice-showcase-host: runs Lattice with the showcase
compose.yaml             Postgres for development and tests
tests/                   core tests
```
