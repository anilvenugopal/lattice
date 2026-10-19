---
title: Access control
summary: Users, roles and permissions; what a permission protects and how to check it; scoping rows in the query; and what the server checks for you.
order: 70
keywords: security roles permissions permission require can 403 row scoping access boundary csrf admin editor viewer
---

Access in Lattice has two parts:

- **Permissions** decide which features a user can use: pages, lists, actions,
  Ctrl+J sources, help topics, parts of a page.
- **Each list's query** decides which records a user can see.

Both are checked on the server. Hiding a button is never the check.

## Users, roles and permissions

| Idea | What it is | Example | Who sets it |
|---|---|---|---|
| **User** | A person who can sign in | `editor@example.com` | Administrators, in Administration › Users |
| **Permission** | One thing someone may do | `showcase.items.edit`: create, edit, assign and change items | **Developers**, in the app's manifest |
| **Role** | A named set of permissions | Editor; or a custom "Auditor" with `lattice.audit.view` | **Administrators**, in Administration › Roles |

A user has one or more roles. Their permissions are everything their roles
grant, added together. Code checks a **permission**, never a role name.

Two rules always hold:

- **The admin role has every permission**, including the ones a new app adds.
  It cannot be edited, so nobody can lock everyone out.
- **A user with no role** can sign in but sees only a waiting page until an
  administrator gives them one.

## Declaring permissions

An app declares what its users may do, in its manifest:

```python
EDIT, DELETE = "helpdesk.tickets.edit", "helpdesk.tickets.delete"
PERMISSIONS = [
    Permission(EDIT, "Edit tickets", "Open, assign and close tickets.",
               default_roles=("editor",)),
    Permission(DELETE, "Delete tickets", "Delete tickets for good."),
]

APP = AppManifest(key="helpdesk", …, permissions=PERMISSIONS)
```

| Field | Is |
|---|---|
| `key` | Starts with the app's key: `helpdesk.…`. Dotted lower-case words |
| `label`, `description` | What administrators see when they tick it on a role |
| `default_roles` | Roles that get it the first time `lattice migrate` sees it. After that, only administrators change who has it |

Name permissions after what they allow, not after who has them: write
`helpdesk.tickets.close`, not `helpdesk.managers`. Keep them few: one per
group of actions that the same people do.

## What a permission protects

| Protects | How | Without the permission |
|---|---|---|
| A page (a URL) | `dependencies=[Depends(require(EDIT))]` on the route | 403, even if the URL is typed |
| A menu entry | `NavNode(…, permission=EDIT)` | Not in the rail, sidebar or Ctrl+J |
| A whole list | `GridSpec(…, permission=…)` | Its rows, panel, export, actions and Ctrl+J results are refused |
| One action on rows | `Action(…, permission=EDIT)` | No button, and posting to it directly returns 403 |
| A Ctrl+J source | `SearchProvider(…, permission=…)` | Not shown in Ctrl+J |
| A help topic | `permission: helpdesk.tickets.edit` in its front matter | Not listed; 404 |
| Part of a template | `{% if current_user.can("helpdesk.tickets.edit") %}` | Not drawn |

Leaving `permission` empty means every signed-in user. Each check names one
permission.

A `NavNode`'s permission only hides the menu entry. Put `require` on the route
too, or a user who types the URL gets the page. Grid actions and grid
endpoints check their permissions on the server for you.

**Sections.** A rail icon shows when the user may open at least one page in its
section, and leads to the first such page. Someone who may only read the audit
log sees Administration with just **Audit log** in it.

**Typos stop the host.** `create_app` refuses to start if a page, grid,
action, Ctrl+J source or help topic names a permission that no app declares,
and `require` fails the first request that uses an undeclared one.

## Lattice's own permissions

| Permission | Allows |
|---|---|
| `lattice.users.manage` | Administration › Users |
| `lattice.roles.manage` | Administration › Roles |
| `lattice.sessions.manage` | Administration › Sessions |
| `lattice.audit.view` | Administration › Audit log, and Recent activity on Home |
| `lattice.system.view` | Administration › System and UI kit |
| `lattice.views.share` | Share a saved grid view with everyone, and delete views others shared (default: editor) |

Account, Home, Help and Ctrl+J are open to every signed-in user.

## Row scoping

Roles do not decide which rows a user may see. The grid's query does:

```sql
-- name: grid
-- The signed-in user's messages: each user sees only their own.
SELECT m.id, m.subject, m.received_at
FROM showcase.message m
WHERE m.owner_id = :user_id;
```

The grid fills `:user_id` with the signed-in user's id on every request; nothing
the browser sends can change it.

Everything that reads rows goes through this query:

- the list and its paging;
- the side panel and the Ctrl+J preview;
- actions, including "select all N matching";
- CSV export;
- home tiles.

Rows the query does not return cannot be reached through any of them.

**Your own routes must apply the same scoping.** A detail page, an edit form or
an HTMX endpoint that loads a record by id returns 404 when the user could not
see that record in the list. Put the same condition in the record's own query:

```sql
-- name: by_id
-- One of the signed-in user's messages; no row if it is someone else's.
SELECT id, subject, body, received_at FROM showcase.message
WHERE id = :id AND owner_id = :user_id;
```

```python
message = db.one(SQL.by_id, id=message_id, user_id=request.state.user.id)   # else 404
```

A grid's side panel does not need this: the grid loads the row through its own
query before it calls `panel`.

## What Lattice checks for you

| Check | Where |
|---|---|
| A valid session on every page except sign-in and static files | Middleware |
| A forced password change, and at least one role | Middleware |
| CSRF on every form post, HTMX request and grid action | `csrf_protect` on each router; the grid router |
| The permission of a grid and of each action | Grid endpoints |
| Rows come only from the grid's query | Grid endpoints, panels, export, Ctrl+J |
| `when`: actions run only on eligible rows | Grid action endpoint |
| An administrator cannot remove their own admin role or deactivate themselves | Administration |

## Your responsibilities

- Add `Depends(csrf_protect)` to every router that changes data:
  `APIRouter(dependencies=[Depends(csrf_protect)])`.
- Declare the app's permissions, and add `require(…)` to every route a
  permission must protect.
- Scope rows in the grid's query and in your own record routes.
- Never log or render passwords, session tokens or OIDC tokens.
- Put values in queries as `:placeholders`, never by building SQL text; Lattice's checks fail on SQL written in Python.
- Render user input through Jinja's autoescaping. In an Alpine attribute, use
  the `js` filter: `@click="run({{ key|js }})"`.

Sign-in, sessions and cookies are covered in
[Sign-in and sessions](../running/sign-in.md).
