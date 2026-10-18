---
title: Access control
summary: Roles on routes, pages, grids and actions; scoping rows in the query; and what the server checks for you.
order: 70
keywords: security roles permissions require_roles admins editors viewer 403 row scoping access boundary csrf
---

Access in Lattice has two parts:

- **Roles** decide which functions a user can use: pages, grids, actions.
- **The grid's query** decides which rows a user can see.

Both are checked on the server. Hiding a button is never the check.

## Roles

Lattice has three built-in roles:

| Role | Can |
|---|---|
| `viewer` | Read |
| `editor` | Create and change records, run bulk actions |
| `admin` | Everything an editor can, plus Administration |

`lattice.api` exports two constants. Use them instead of role strings:

| Constant | Is |
|---|---|
| `EDITORS` | `("admin", "editor")` |
| `ADMINS` | `("admin",)` |

A user with no role cannot use the app at all. They see a waiting page until an
administrator grants one.

> [!NOTE]
> Permissions declared by apps will replace role checks in a later step
> ([Decisions and direction](../architecture/decisions.md)). Code written with
> `EDITORS` and `ADMINS` will then move to permissions.

## Where to put role checks

| Protects | How | An empty value means |
|---|---|---|
| A route | `dependencies=[Depends(require_roles(*EDITORS))]`; returns 403 | — |
| A page in the menus | `NavNode(…, roles=EDITORS)` | Every signed-in user |
| A whole grid | `GridSpec(…, roles=ADMINS)`: its rows, panel, actions, export and Ctrl+J results | Every signed-in user |
| One action | `Action(…, roles=EDITORS)` | Everyone who can see the grid |
| A Ctrl+J source | `SearchProvider(…, roles=…)` | Everyone |
| A help topic | `roles: [admin]` in its front matter | Everyone |
| Part of a template | `{% if current_user.has_any(EDITORS) %}`, with `EDITORS` passed in | — |

A `NavNode`'s `roles` only hides the menu item. Put `require_roles` on the
route as well, or a user who types the URL gets the page. Grid actions and
grid endpoints check their roles on the server for you.

In a template, pass a flag from the route rather than checking roles in the
template, as the demo's detail page does:

```python
can_edit=request.state.user.has_any(EDITORS)
```

## Row scoping

Roles do not decide which rows a user may see. The grid's query does:

```python
def query(db, user):
    return (select(Message.id, Message.subject, Message.received_at)
            .where(Message.owner_id == user.id))          # each user sees only their own
```

Everything that reads rows goes through this query:

- the list and its paging;
- the side panel and the Ctrl+J preview;
- actions, including "select all N matching";
- CSV export;
- home tiles.

Rows the query does not return cannot be reached through any of them.

**Your own routes must apply the same scoping.** A detail page, an edit form or
an HTMX endpoint that loads a record by id returns 404 when the user could not
see that record in the list. One way is to reuse the query:

```python
def get_visible(db, user, message_id):
    sub = query(db, user).subquery()
    row = db.execute(select(sub).where(sub.c.id == message_id)).first()
    if row is None:
        raise HTTPException(404)
    return row
```

## What Lattice checks for you

| Check | Where |
|---|---|
| A valid session on every page except sign-in and static files | Middleware |
| A forced password change, and at least one role | Middleware |
| CSRF on every form post, HTMX request and grid action | `csrf_protect` on each router; the grid router |
| The roles of a grid and of each action | Grid endpoints |
| Rows come only from the grid's query | Grid endpoints, panels, export, Ctrl+J |
| `when`: actions run only on eligible rows | Grid action endpoint |
| An administrator cannot remove their own admin role or deactivate themselves | Administration |

## Your responsibilities

- Add `Depends(csrf_protect)` to every router that changes data:
  `APIRouter(dependencies=[Depends(csrf_protect)])`.
- Add `require_roles` to every route that a role must protect.
- Scope rows in the grid's query and in your own record routes.
- Never log or render passwords, session tokens or OIDC tokens.
- Use bind parameters (SQLAlchemy does this) and never build SQL from strings.
- Render user input through Jinja's autoescaping. In an Alpine attribute, use
  the `js` filter: `@click="run({{ key|js }})"`.

Sign-in, sessions and cookies are covered in
[Sign-in and sessions](../running/sign-in.md).
