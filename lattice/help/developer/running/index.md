---
title: Running Lattice
summary: Create a host, configure it, and run it outside development, with a checklist for production.
order: 50
keywords: deploy deployment production host configuration environment uvicorn proxy https checklist operations
---

A **host** is the program you run. It is a small Python package that lists
its apps and, optionally, a folder of branding. This section covers creating
one, configuring it and running it.

| Page | Covers |
|---|---|
| [Sign-in and sessions](sign-in.md) | Password and OIDC sign-in, account linking, sessions, cookies, CSRF |
| [Users and roles](users-and-roles.md) | The first administrator, roles, and managing users |
| [Branding a host](branding.md) | Name, logos, colours and fonts, page overrides, slots and icons |

## A host

The demo host is the shape to copy:

```text
hosts/helpdesk/
  pyproject.toml          depends on lattice and the apps it runs
  helpdesk_host/
    __init__.py
    main.py               app = create_app(apps=[…], host_dir=…)
    templates/            optional page overrides and slot templates
    static/               optional theme.css and logo files
```

```python
"""The helpdesk host."""

from pathlib import Path

import lattice_helpdesk
from lattice.host import create_app

app = create_app(apps=[lattice_helpdesk.APP], host_dir=Path(__file__).parent)
```

`create_app` returns a FastAPI application. Point `LATTICE_HOST` at it
(`helpdesk_host.main:app`), and the `lattice` command migrates, seeds and runs
that host.

The rail lists Home, then the apps in the order of the `apps` list, then
Administration and Account.

## Configuration

Settings are environment variables starting with `LATTICE_`, read from the
environment first and then from a `.env` file in the working folder. Each one
is listed with its default in [Reference › Settings](../reference/settings.md).

The ones every deployment sets:

| Setting | Set it to |
|---|---|
| `LATTICE_APP_ENV` | `production` |
| `LATTICE_SECRET_KEY` | A long random value: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `LATTICE_DATABASE_URL` | The database (see below) |
| `LATTICE_HOST` | Your host, as `module:attribute` |
| `LATTICE_APP_NAME`, logos | Your product's name and logos; see [Branding a host](branding.md) |
| `LATTICE_OIDC_*` | Your identity provider; see [Sign-in and sessions](sign-in.md) |

`LATTICE_APP_ENV=production` does four things:

- turns off the API docs page (`/docs`);
- hides the development accounts on the sign-in page;
- makes `lattice seed` refuse to run;
- makes every cookie `Secure`.

The status bar shows the environment, so users can tell production from test.

**Administration › System** shows the running configuration: the environment,
the database, the sign-in methods, the session limits, every grid and every page.

## The database

Lattice needs **Postgres** (version 17 is what development and tests use).
One database holds everything: Lattice's tables in the `lattice` schema, and
each app's in a schema named after its key. Point `LATTICE_DATABASE_URL` at it:

```bash
LATTICE_DATABASE_URL=postgresql+psycopg://lattice:secret@db.internal:5432/lattice
```

The database user needs to create schemas and tables in that database, for
the migrations. Lattice opens one connection pool per process.

Apply migrations before each release starts serving:

```bash
uv run lattice migrate
```

It applies Lattice's pending migration files, then each app's, in one
transaction, and prints what it applied. Two runs at once wait for each other.

Back up the database with Postgres's own tools, for example a nightly
`pg_dump`, or your managed service's snapshots, and test a restore.

## Running the server

In development, `lattice dev` runs uvicorn with auto-reload. Outside
development, run uvicorn directly:

```bash
uv run uvicorn helpdesk_host.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips=10.0.0.5
```

- **Behind a proxy.** When a reverse proxy or load balancer terminates TLS,
  pass `--proxy-headers` and the proxy's address in `--forwarded-allow-ips`, so
  Lattice sees the original `https` scheme and client address.
- **Health checks.** `GET /health` needs no sign-in. It answers
  `{"status": "ok"}` after a query to the database.
- **Workers.** Run several workers (`--workers 4`) for more traffic. Each worker
  has its own connection pool, and runs every app's `background` task.
- **Slow grids.** A grid query running longer than
  `LATTICE_GRID_QUERY_TIMEOUT_SECONDS` (15) is cancelled, and the user is asked
  to narrow the search. See [Grid performance](../building-apps/grid-performance.md).

## Production checklist

- [ ] `LATTICE_APP_ENV=production`
- [ ] `LATTICE_SECRET_KEY` set to a long random value, kept secret, and the same in every process
- [ ] Served over HTTPS; uvicorn started with `--proxy-headers` behind a proxy
- [ ] Postgres reachable at `LATTICE_DATABASE_URL`, with backups scheduled and a restore tested
- [ ] `lattice migrate` run for this release
- [ ] A first administrator created with `lattice create-user` ([Users and roles](users-and-roles.md))
- [ ] OIDC configured and tested, and `LATTICE_OIDC_DEFAULT_ROLE` chosen ([Sign-in and sessions](sign-in.md))
- [ ] `LATTICE_PASSWORD_LOGIN_ENABLED=false` if everyone signs in through SSO
- [ ] Name, logos and theme set ([Branding a host](branding.md))
- [ ] `/health` wired to your monitoring
