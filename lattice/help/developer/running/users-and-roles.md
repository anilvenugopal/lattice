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

## The built-in roles

| Role | Label | Can |
|---|---|---|
| `admin` | Administrator | Everything, plus Administration: users, roles, sessions, audit log |
| `editor` | Editor | Create and change records; run bulk actions |
| `viewer` | Viewer | Read every page outside Administration |

**What roles control.** Roles decide which functions a user can use, not which
records they see. Apps scope records in their grids' queries (see
[Access control](../building-apps/access-control.md)).

**No role, no access.** A user with no role sees only a waiting page.

**Protecting the last administrator.** Administrators cannot remove their own
admin role or deactivate themselves, so a host always keeps at least one.

## Adding a role

Roles are rows in the `lattice.role` table, added by migrations:

1. **Write a migration** in Lattice's schema folder. Create the file with
   `make migration schema=lattice m="add auditor role"`, then fill it in:

   ```sql
   -- lattice/sql/schema/0002_add_auditor_role.sql
   -- The auditor role: reads the audit log.

   INSERT INTO lattice.role (code, label, sort_order, description)
   VALUES ('auditor', 'Auditor', 4, 'Read the audit log.');
   ```

2. **Add a constant** in `lattice/kernel/auth/roles.py`, and export it from
   `lattice.api`. Apps use the constant, never the string.
3. **Use it** in `roles=` and `require_roles(...)`.

Administrators then grant it in **Administration › Users**. Roles are listed
in **Administration › Roles**.

> [!NOTE]
> Roles will become named sets of permissions that apps declare
> ([Decisions and direction](../architecture/decisions.md)).

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
