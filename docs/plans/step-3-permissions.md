# Step 3 plan: permissions instead of role checks

Status: **done** on the `step-3` branch (18 October 2026), with the recommended answer to every decision below and the differences listed at the end.

## The problem

Lattice checks three fixed roles by name: `admin`, `editor`, `viewer`. That
breaks down with several apps:

- **Mixed jobs.** An editor of the Work Queue is not necessarily an editor of
  the Jobs app.
- **No new roles without code.** An "auditor" who may only read the audit log
  can't be made without changing code.
- **No way to add rights.** Each new app would have to invent more fixed roles.

Today about 80 checks in 19 files name roles directly (`roles=EDITORS`,
`require_roles(*ADMINS)`).

## What step 3 delivers ([ADR 0009](../adr/0009-permissions.md))

- **Apps declare permissions** in their manifest, for example
  `demo.work.edit`: "Create, edit, assign and approve work items".
- **A role is a named set of permissions.** Administrators create and edit
  roles in **Administration › Roles**, ticking permissions grouped by app. No
  code change is needed to make an "auditor" role.
- **Every check names a permission, never a role.** That covers routes, menu
  entries, grids, grid actions, Ctrl+J sources, help topics and templates.
- **Typos are caught.** `create_app` refuses to start if any check names a
  permission that no app declares.

## How it looks

```python
APP = AppManifest(
    key="demo", …,
    permissions=[
        Permission("demo.work.edit", "Edit work items",
                   "Create, edit, assign and approve work items.", default_roles=("editor",)),
        Permission("demo.work.delete", "Delete work items",
                   "Delete work items for good."),
    ],
)

Action("approve", "Approve", handler=approve, permission="demo.work.edit")
NavNode("work.new", "New item", "/demo/work/new", parent="work", permission="demo.work.edit")

@router.get("/work/new", dependencies=[Depends(require("demo.work.edit"))])
```

In templates: `{% if current_user.can("demo.work.edit") %}`. In help topics,
front matter `permission: lattice.audit.view`.

| Check | Today | Step 3 |
|---|---|---|
| A route | `require_roles(*EDITORS)` | `require("demo.work.edit")` |
| Menu entry, grid, action, Ctrl+J source | `roles=EDITORS` | `permission="demo.work.edit"` |
| Template | `current_user.has_any(...)` | `current_user.can("…")` |
| Help topic | `roles: [admin]` | `permission: lattice.users.manage` |
| Nothing set | Every signed-in user | Every signed-in user (unchanged) |

## Where things are stored

| What | Where | Why |
|---|---|---|
| The permissions that exist (the catalogue) | Code: each app's manifest | They exist because the code checks them |
| Which role has which permission | Database: `lattice.role_permission` | Administrators change it without a release |
| The roles | Database: `lattice.role` (as today) | Administrators add roles |

**New permissions get their default roles once.** When an app adds a
permission, `lattice migrate` records it in `lattice.permission` and grants it
to its `default_roles`, the first time only. After that, administrators
decide. An administrator's change is never overwritten by a deploy.

**Sign-in loads the user's permissions once per request**, with the session,
as one query. `current_user.can(...)` costs nothing.

## Lattice's own permissions

| Permission | Allows | Default role |
|---|---|---|
| `lattice.users.manage` | Administration › Users: create, edit, roles, deactivate, reset passwords | admin |
| `lattice.roles.manage` | Administration › Roles: create and edit roles and their permissions | admin |
| `lattice.sessions.manage` | Administration › Sessions: see and revoke anyone's sessions | admin |
| `lattice.audit.view` | Administration › Audit log | admin |
| `lattice.system.view` | Administration › System and UI kit | admin |

Account pages, Home, Help and Ctrl+J stay open to every signed-in user. The
demo app declares `demo.work.edit` and `demo.work.delete`.

## Stages

On a branch, `step-3`, one commit per stage, merged when you approve.

| # | Stage | Contents |
|---|---|---|
| 1 | **Catalogue and storage** | `Permission`; `AppManifest.permissions`; migration `0002` with `lattice.permission` and `lattice.role_permission`; `lattice migrate` records new permissions and grants their defaults once; `CurrentUser.permissions` and `can()`; `require()` |
| 2 | **Every check names a permission** | Replace all role checks in Lattice, the demo, templates and help; declare Lattice's and the demo's permissions; `create_app` refuses unknown or wrongly named permissions; remove `ADMINS`, `EDITORS` and `require_roles` from `lattice.api` |
| 3 | **The roles editor** | Administration › Roles: create a role, tick its permissions grouped by app, edit and delete roles, all audited; see a role's members |
| 4 | **Docs** | Access control, Users and roles, the Administration user guide, Reference, AGENTS.md, the add-grid-page skill, the tutorial (rebuilt and tested again), ADR 0009 accepted, ARCHITECTURE.md |

The full suite passes at the end of stage 2 and after each later stage.

## Not in step 3

- **Scoped permissions** (`taskline.operate@prod`). They need bindings to
  separate databases, which are not built. They come with the taskline Ops
  console.
- **Row-level permissions.** Which rows a user sees stays in each grid's query,
  as ADR 0009 decided.

## Decisions (approved)

1. **The admin role always has every permission.** It can't be edited, so a new
   app's permissions are never out of administrators' reach and nobody can lock
   themselves out.
2. **One Lattice permission per Administration area:** the five in the table above.
3. **One permission per check.** No "any of these" lists.
4. **Editor and viewer are editable** like any role, but can't be deleted.

## How the result differs from this plan

| Plan | Built | Why |
|---|---|---|
| — | A rail section shows when the user may open at least one of its pages; its icon and breadcrumb lead to the first such page | With one permission per Administration area, an auditor's Administration icon must not lead to Users, which they can't open |
| — | The demo's **New item** menu entry needs `demo.work.edit` | It showed to everyone though only editors could open the page |
| `create_app` refuses unknown permissions | It does for pages, grids, actions, Ctrl+J sources and help topics; `require(...)` on a route fails at its first request | A route's dependency can't be inspected when the host starts |
| Delete roles | Only roles that are not built in and have no members | Deleting a role with members would silently take access away |
| — | A help topic still using `roles:` is refused with a pointer to `permission:` | Old topics fail loudly instead of becoming visible to everyone |
| — | The Administration user-guide topic needs `lattice.users.manage` | It is about managing users |

