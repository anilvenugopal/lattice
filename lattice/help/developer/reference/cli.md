---
title: Command line
summary: The lattice command: migrations, users, seed data, the development server and these docs.
order: 50
keywords: cli command migrate seed create-user dev docs
---

> [!NOTE]
> Generated from `lattice/cli.py` by `lattice docs build`. Change the code, not this page.

The Lattice command line. Run it with `uv run lattice …` from the repository root.

## migrate

Apply database migrations.

```text
lattice migrate [-h]
```

## new-migration

Create the next numbered migration file for a schema.

```text
lattice new-migration [-h] schema description
```

| Argument | Description |
|---|---|
| `schema` | Lattice, or an app's key such as demo. |
| `description` | What changes, e.g. "add ticket table". |

## reset

Drop and rebuild the development database, then seed it (refused in production).

```text
lattice reset [-h]
```

## create-user

Create or update a user (first admin).

```text
lattice create-user [-h] [--role ROLE] [--no-password]
                           [--keep-password]
                           email name
```

| Argument | Description |
|---|---|
| `email` | Sign-in email; an existing user with it is updated. |
| `name` | Display name. |
| `--role` | Repeatable, e.g. --role admin. |
| `--no-password` | No password: the user signs in with SSO only. |
| `--keep-password` | Do not force a change at sign-in. |

## seed

Development users and example data.

```text
lattice seed [-h]
```

## dev

Run the host with reload.

```text
lattice dev [-h] [--port PORT]
```

| Argument | Description |
|---|---|
| `--port` | Default: `8000`. |

## docs

Regenerate the Reference pages of the documentation.

```text
lattice docs [-h] {build,check}
```

| Argument | Description |
|---|---|
| `action` | Build writes the pages; check fails if they are out of date. One of: build, check. |
