---
title: Getting started
summary: Run Lattice and its demo app on your machine, and find your way around the repository.
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

You do not need Node.js, Docker or a database server. Development uses a SQLite
file in `data/`.

## Run it

```bash
git clone https://github.com/anilvenugopal/lattice.git
cd lattice
make setup
make dev
```

`make setup` runs three commands:

| Command | What it does |
|---|---|
| `uv sync --all-packages` | Creates `.venv` and installs Lattice, the demo app and the demo host |
| `uv run lattice migrate` | Creates `data/lattice.db` and applies the database migrations |
| `uv run lattice seed` | Adds the development users and the demo app's example data |

`make dev` starts the demo host with auto-reload at
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
   the demo app's Work Queue, Jobs and Inbox, then Administration and Account
   at the bottom.
2. **A grid.** Open **Work Queue**:
   - switch views with the tabs;
   - filter by status and type in the search box;
   - select a few rows and choose **Assign**.
   The action asks for an owner, updates the rows and shows a toast. The URL
   keeps the view, filters and sort, so a link reopens the same list.
3. **Ctrl+J.** Press **Ctrl J** and type `marine`:
   - results come from pages, work items, commands and help;
   - the chips at the top filter by source;
   - the pane on the right previews the highlighted result.
4. **F1.** On the Work Queue, press **F1**. Help opens at the topic for that
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
apps/demo/               lattice-demo: the example app and its tests
hosts/demo/              lattice-demo-host: runs Lattice with the demo app
alembic/                 database migrations
tests/                   tests of the core
docs/                    architecture and decision records
```

The demo app in `apps/demo/` is the best source of working examples. It shows
three shapes of list:

- **Work Queue** (`work_items.py`): a table with views, bulk actions, a side
  panel, a detail page and forms;
- **Jobs** (`jobs.py`): a list that refreshes itself, with actions that
  depend on each row's state;
- **Inbox** (`inbox.py`): a message list with a reading pane.

## Everyday commands

| Command | Use it to |
|---|---|
| `make dev` | Run the host with auto-reload |
| `make test` | Run every test, core and apps. Run it before you hand off a change |
| `make lint` | Run ruff and the import rules (apps import only `lattice.api`, and so on) |
| `make revision m="add note table"` | Create a migration from model changes |
| `make migrate` | Apply new migrations |
| `make reset` | Delete the development database and set it up again |
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
| `no such table` on the first page | Run `make migrate`, then restart `make dev` |
| Cannot sign in with the accounts above | The database was created before seeding. Run `make seed`, or `make reset` to start over |
| `AppError: App 'x': …` when the host starts | An app broke a rule; the message names the rule. See [App manifest](../reference/app-manifest.md) |
| `AppError: Help for 'x', …` | A help topic has a broken link or front matter; the message names the file |
| Port 8000 in use | `uv run lattice dev --port 8001` |

## Next

[Your first app](first-app.md) builds a Notes app: a table, a list page, a
form, help topics and tests.
