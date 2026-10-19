---
title: Getting started
summary: Run Lattice and its showcase on your machine, and find your way around the repository.
order: 20
keywords: install setup run local development quickstart make uv
---

This page takes you from a fresh clone to a running Lattice in about five
minutes. Then [Your first app](first-app.md) builds a small app on it.

## Before you start

You need:

- **Python 3.14**. uv can install it for you: `uv python install 3.14`.
- **[uv](https://docs.astral.sh/uv/)** 0.11 or later. It manages the virtual environment and the workspace packages.
- **make** and **git**.
- **A container tool for Postgres:** podman with `podman-compose` (the default),
  or Docker with Compose (run `make` with `COMPOSE="docker compose"`).

You do not need Node.js or a Postgres install of your own. `compose.yaml` runs
Postgres 17 in a container, on port 5436, with its data in a volume.

## Run it

```bash
git clone https://github.com/anilvenugopal/lattice.git
cd lattice
make db-up
make setup
make dev
```

`make db-up` starts Postgres and waits until it accepts connections. You start
it once; it keeps running until `make db-down`, and its data survives restarts.

`make setup` runs three commands:

| Command | What it does |
|---|---|
| `uv sync --all-packages` | Creates `.venv` and installs Lattice, the showcase app and its host |
| `uv run lattice migrate` | Creates the `lattice` and `showcase` schemas and their tables |
| `uv run lattice seed` | Adds the development users and the showcase's sample data |

`make dev` starts the showcase host with auto-reload at
<http://localhost:8000>.

Sign in with one of the development accounts:

| Email | Password | Roles |
|---|---|---|
| `admin@example.com` | `Admin12345!` | admin, editor |
| `editor@example.com` | `Editor12345!` | editor |
| `viewer@example.com` | `Viewer12345!` | viewer |

> [!NOTE]
> The sign-in page lists these accounts only when `LATTICE_APP_ENV` is
> `development`, and `lattice seed` refuses to run in production.

## Take the tour

Signed in as the admin, try these. Each one shows a part of Lattice that your
apps get for free.

1. **The rail.** The icons on the left are the apps and their sections: Home,
   the showcase's Overview, Grids, Reading pane, Charts, Forms and Flows, then
   Administration and Account at the bottom. **Overview** links every page.
2. **A grid.** Open **Grids › Items**:
   - switch views with the tabs;
   - filter by status and type in the search box;
   - select a few rows and choose **Assign**.
   The action asks for an owner, updates the rows and shows a toast. The URL
   keeps the view, filters and sort, so a link reopens the same list.
3. **Ctrl+J.** Press **Ctrl J** and type `pipeline`:
   - results come from pages, items, commands and help;
   - the chips at the top filter by source;
   - the pane on the right previews the highlighted result.
4. **F1.** On Items, press **F1**. Help opens at the topic for that
   page.
5. **Theme.** Use the moon icon in the top bar, or **Account › Preferences**,
   to switch light, dark or system. Density, page size and time format are
   there too.
6. **Administration.** Look at **Users**, **Audit log** (every action you just
   took is in it) and **UI kit**, which shows every shared component.

## Find your way around

```text
lattice/                 the core package
  api.py                 the only module apps import
  kernel/                auth, users, navigation, database, rendering, icons, slots
  components/            the grid, Ctrl+J search, help, home tiles, AppManifest
  platform/              Lattice's own apps: home, account, admin
  host.py                create_app: checks and registers apps
  cli.py                 the lattice command
  testing.py             pytest fixtures for core and app tests
  help/                  these docs
  templates/  static/    shell layout and macros; CSS and JavaScript
apps/showcase/           lattice-showcase: every component on sample data, and its tests
hosts/showcase/          lattice-showcase-host: runs Lattice with the showcase
lattice/sql/             Lattice's named queries; sql/schema/ holds its migrations
tests/                   tests of the core
compose.yaml             Postgres for development and tests
docs/                    architecture and decision records
```

The showcase in `apps/showcase/` is the best source of working examples, one
module per page:

- **Items** (`items.py`, `sql/items.sql`): a table grid with every column kind,
  bulk actions and a side panel; the record page; the plain form pattern;
- **Live updates** (`jobs.py`): a grid that refreshes itself, with actions that
  depend on each row's state;
- **Reading pane** (`inbox.py`): a message list with a reading pane;
- **Charts** (`charts.py`), **Specs and Free-form** (`specs.py`) and **Flows**
  (`flows.py`).

## Everyday commands

| Command | Use it to |
|---|---|
| `make dev` | Run the host with auto-reload |
| `make test` | Run every test, core and apps. Run it before you hand off a change |
| `make lint` | Run ruff and the import rules (apps import only `lattice.api`, and so on) |
| `make db-up`, `make db-down` | Start or stop Postgres |
| `make migration schema=showcase m="add note table"` | Create the next numbered migration file for a schema |
| `make migrate` | Apply new migrations |
| `make reset` | Drop Lattice's and the apps' schemas, then migrate and seed again |
| `uv run lattice docs build` | Regenerate the [Reference](../reference/index.md) after changing code it documents |

Always run Python through `uv run …` (or `make`). A bare `python` or `pytest`
misses the workspace environment.

## Settings

Settings are environment variables that start with `LATTICE_`. Every one has a
working development default, so you need none to start. To change them, copy
`.env.example` to `.env` and edit it. The full list is in
[Settings](../reference/settings.md).

## If something goes wrong

| Symptom | Fix |
|---|---|
| `lattice: command not found` | Run it as `uv run lattice …`, or use the `make` targets |
| `connection refused` on port 5436 | Postgres is not running: `make db-up` |
| `relation "…" does not exist` | Run `make migrate`, then restart `make dev` |
| Cannot sign in with the accounts above | The database was created before seeding. Run `make seed`, or `make reset` to start over |
| `AppError: App 'x': …` when the host starts | An app broke a rule; the message names the rule. See [App manifest](../reference/app-manifest.md) |
| `AppError: Help for 'x', …` | A help topic has a broken link or front matter; the message names the file |
| Port 8000 in use | `uv run lattice dev --port 8001` |
| Port 5436 in use | Another Postgres is there. Change the port in `compose.yaml` and `LATTICE_DATABASE_URL` |

## Next

[Your first app](first-app.md) builds a Notes app: a table, a list page, a
form, help topics and tests.
