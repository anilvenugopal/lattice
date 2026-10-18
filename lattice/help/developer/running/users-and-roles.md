---
title: Users and roles
summary: Create the first administrator, understand the built-in roles, add a role, and manage users from the command line.
order: 20
keywords: users roles admin administrator first user create-user grant role viewer editor
---

## The first administrator

A new database has no users. Create the first administrator from the command
line:

```bash
uv run lattice migrate
uv run lattice create-user you@example.com "Your Name" --role admin
```

The command asks for a password twice and checks it against the password
policy. That user must change the password at first sign-in, unless you pass
`--keep-password`.

For an SSO-only administrator, pass `--no-password`. The user then signs in
through OIDC, and the account is matched by email on the first sign-in.

`create-user` also updates an existing user: it can reactivate the account,
set a new password, or add roles. Every option is listed in
[Reference › Command line](../reference/cli.md).

After that, administrators manage users in the browser, under
**Administration › Users**. See [Administration](../../user-guide/administration.md)
in the user guide.

## Roles and permissions

A role is a named set of permissions. Apps declare the permissions (see
[Access control](../building-apps/access-control.md)); administrators decide
which roles have them.

| Role | Has |
|---|---|
| `admin` (Administrator) | **Every permission, always**, including ones a new app adds. Cannot be edited |
| `editor` (Editor) | The permissions apps give it by default, such as `demo.work.edit`. Editable |
| `viewer` (Viewer) | None by default: it can read every page that needs no permission. Editable |

**What roles control.** Roles decide which features a user can use, not which
records they see. Apps scope records in their grids' queries.

**No role, no access.** A user with no role sees only a waiting page.

**Protecting the last administrator.** Administrators cannot remove their own
admin role or deactivate themselves, so a host always keeps at least one.

## Making a role

Administrators make roles in the browser, with no code change:

1. **Administration › Roles › New role.** Give it a code (`auditor`), a name and
   a description.
2. **Tick its permissions**, grouped by app, for example **Read the audit log**.
3. **Give it to people** in **Administration › Users** (**Grant role**, or on
   the user's page).

A role's page also edits its permissions later and lists its members. Changes
are audited. Built-in roles cannot be deleted; a role you made can be deleted
once nobody has it.

## Where permissions come from

When an app adds a permission, `make migrate` records it and gives it to the
roles the app suggests (`default_roles`), **once**. From then on, only
administrators change who has it, and a later deploy never undoes their
changes. `make migrate` prints the new permissions.

## Development users

`lattice seed` creates these users in a development database, and never in
production:

| Email | Password | Roles |
|---|---|---|
| `admin@example.com` | `Admin12345!` | admin, editor |
| `editor@example.com` | `Editor12345!` | editor |
| `viewer@example.com` | `Viewer12345!` | viewer |
| `sam.ortiz@example.com` | none (SSO only) | editor |
| `priya.nair@example.com` | none (SSO only) | editor |

App tests sign in as their own users from the `users` fixture (see
[Testing](../building-apps/testing.md)).
