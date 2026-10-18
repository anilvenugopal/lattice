---
title: Pages and navigation
summary: Declare pages with NavNode, render them with render_page, and build list, detail, form and settings pages.
order: 10
keywords: navnode nav rail sidebar breadcrumb render_page page layout detail crumb hidden template shell
---

Every page in Lattice has two halves:

- a **`NavNode`** in the app's manifest, which says where the page sits in the navigation;
- a **route** that renders it with `render_page`.

The shell builds the rail, sidebar, breadcrumbs, page title, Ctrl+J page
results and the F1 target from the nav nodes. You never write menus.

## Declaring pages

```python
nav=[
    NavNode("tickets", "Tickets", "/helpdesk/tickets", icon="inbox",
            keywords="cases requests", description="Customer tickets"),
    NavNode("tickets.open", "Open", "/helpdesk/tickets?view=open", parent="tickets"),
    NavNode("tickets.all", "All tickets", "/helpdesk/tickets", parent="tickets"),
    NavNode("tickets.new", "New ticket", "/helpdesk/tickets/new", parent="tickets",
            roles=EDITORS),
    NavNode("tickets.detail", "Ticket", "/helpdesk/tickets", parent="tickets.all", hidden=True),
    NavNode("reports", "Reports", "/helpdesk/reports", icon="activity", roles=ADMINS),
]
```

Each part of the shell comes from these nodes:

| Part of the shell | Built from |
|---|---|
| **Rail** (icons on the left) | Top-level nodes (`parent=None`), in manifest order. `bottom=True` puts a node in the bottom group |
| **Sidebar** | The visible children of the active top-level node. A section with fewer than two visible children has no sidebar |
| **Breadcrumbs** | The chain of parents from the active node, plus `crumb=` if the route passes one |
| **Browser tab title** | `crumb`, else a `title` the route passes, else the active node's label |
| **Ctrl+J pages** | Every visible node the user may open, matched on label, `keywords` and `description` |
| **F1** | The node's key, looked up in the app's `help.toml` |

`roles=` hides a node from users without one of the roles. Hiding a node does
not protect its route: protect the route with `require_roles` too (see
[Access control](access-control.md)).

`hidden=True` makes a node that never shows in a menu but still resolves the
breadcrumbs and keeps its parent highlighted. Use it for detail and edit pages.

Nav keys are unique across the host. Keep them short and prefix them with the
area (`tickets.new`), not the app key.

## Rendering a page

```python
@router.get("/tickets/{ticket_id}")
def detail(ticket_id: int, request: Request, db: Db = Depends(get_db)):
    ticket = db.one(SQL.by_id, id=ticket_id)          # a dict; 404 if there is none
    return render_page(request, "helpdesk/ticket_detail.html", "tickets.detail",
                       ticket=ticket, events=audit.history(db, "helpdesk.tickets", ticket_id),
                       crumb=ticket["ref"])
```

`render_page(request, template, nav_key, *, status_code=200, **context)`
renders the template inside the shell. The context is passed as keyword
arguments. For HTMX partials, which have no shell, use
`render(request, template, **context)`.

Every template that renders a full page extends the shell and fills `main`:

```jinja
{% extends "base/shell.html" %}
{% from "components/macros.html" import page_header, card %}
{% block main %}
<div class="page">
  {{ page_header("Reports", "Weekly ticket volume") }}
  …
</div>
{% endblock %}
```

Templates can always use these globals:

| Global | Is |
|---|---|
| `current_user` | The signed-in `CurrentUser` (`display_name`, `email`, `roles`, `has_any(roles)`) |
| `csrf_field()` | The hidden CSRF input for forms |
| `icon(name, size)` | An inline SVG icon |
| `time_tag(value, mode)` | A `<time>` element the browser formats in the user's time zone |
| `label_for`, `tone_for` | A grid column's label and tone for a value |
| `fmt(template, row)`, `fmt_url(template, row)` | Fill `{key}` placeholders from a row |
| `prefs.get(current_user, key)` | A user preference |
| `settings` | Lattice's settings |
| Filters `number`, `money`, `js` | Number formatting; a value as a safe JavaScript literal in an Alpine attribute |

## Page types

Build every page as one of these types. Users then find the same things in the
same places on every page.

| Type | How | Example |
|---|---|---|
| **List** | `render_grid_page(request, db, GRID, nav_key)`. See [Grids](grids.md) | `/demo/work`, `/admin/users` |
| **List and reader** | The same, with `layout="split"` on the grid | `/demo/inbox` |
| **Record (detail)** | `page_header` with the status and actions, `card`s with `prop_list`, and a `timeline` of activity | `/demo/work/1`, `/admin/users/1` |
| **Form** | `page page--narrow`, a `card` of `field`s, then `form-actions`. See [Forms and feedback](forms-and-feedback.md) | `/demo/work/new` |
| **Settings** | `card`s of `pref_row`s | `/account/preferences` |
| **Dashboard** | `stat` tiles, then a `grid-2` of cards | `/` |

Page containers and layout helpers:

| Class | Use |
|---|---|
| `.page` | The default page container |
| `.page--narrow` | Forms and settings (760px) |
| `.page--fill` | A grid that fills the viewport |
| `.stack`, `.stack-lg` | Vertical spacing between children |
| `.cluster` | A wrapping row of items |
| `.grid-2`, `.grid-2--wide-left`, `.grid-2--tight` | Two columns |
| `.form-actions` | The button row under a form |

## A detail page

The record page pattern, from `apps/demo/lattice_demo/templates/demo/work_item_detail.html`:

```jinja
{% extends "base/shell.html" %}
{% from "components/macros.html" import page_header, card, prop_list, badge_for, timeline %}
{% block main %}
<div class="page">
  {% set status_col = spec.column("status") %}
  {% call page_header(item.ref ~ " · " ~ item.title, item.account,
                      label_for(status_col, item.status), tone_for(status_col, item.status)) %}
    <a class="btn btn--ghost" href="/demo/work">{{ icon('chevron-left', 14) }}Back to list</a>
    {% if can_edit %}<a class="btn btn--primary" href="/demo/work/{{ item.id }}/edit">Edit</a>{% endif %}
  {% endcall %}
  <div class="grid-2 grid-2--wide-left">
    {% call card("Details") %}
      {{ prop_list([("Reference", item.ref),
                    ("Status", badge_for(status_col, item.status)),
                    ("Received", time_tag(item.received_at, "datetime"))], columns=2) }}
    {% endcall %}
    {% call card("Activity") %}{{ timeline(events) }}{% endcall %}
  </div>
</div>
{% endblock %}
```

Three rules for detail pages:

- **Same rows as the list.** The route must apply the same row scoping as
  the grid's `query`. If a user cannot see a row in the list, the detail route
  returns 404 for it.
- **Status from the column.** Show the status with
  `badge_for(spec.column("status"), value)`, so the label and tone match the
  list.
- **Breadcrumb.** Pass `crumb=` with the record's name. Its node is
  `hidden=True`, with the list node as its parent.

## The help link

The shell puts the page's nav key on `<body data-nav-key="…">`. The Help menu
item "Help for this page" and the F1 key open `/help/for/{nav_key}`, which
redirects to the topic mapped in the app's `help.toml`, or to the app's help
home. See [Writing help](writing-help.md).
