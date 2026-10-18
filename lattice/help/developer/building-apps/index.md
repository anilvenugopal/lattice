---
title: Building apps
summary: The anatomy of a Lattice app, the rules every app follows, and a guide to each part.
order: 40
keywords: app package manifest rules conventions structure
---

An app is a Python package that exports one `AppManifest` named `APP`. This
section explains each part of an app in depth. If you have not built one yet,
start with [Your first app](../getting-started/first-app.md).

## Anatomy of an app

```text
apps/helpdesk/                    the distribution: lattice-helpdesk
  pyproject.toml                  depends on "lattice" only
  lattice_helpdesk/               the package
    __init__.py                   APP = AppManifest(key="helpdesk", …)
    models.py                     SQLAlchemy tables (Base from lattice.api)
    tickets.py                    one module per area: query, GridSpec, actions, routes
    seed.py                       example data for `lattice seed` (optional)
    templates/helpdesk/           Jinja templates, only in a folder named after the key
    static/helpdesk.css           styles scoped to [data-app="helpdesk"] (optional)
    help/                         Markdown topics and help.toml
  tests/
    conftest.py                   host_apps fixture returning [APP]
    test_tickets.py
```

## The rules

`create_app` and the tests enforce most of these; reviews catch the rest.

| Rule | Enforced by |
|---|---|
| Import only `lattice.api`, never another app | `make lint` (import contracts) |
| The key is lowercase letters, digits and underscores, and not reserved | `create_app` |
| Nav routes and grid paths start with `/{key}`; grid keys start with `{key}.` | `create_app` |
| Templates only in `templates/{key}/`; slot templates in `{key}/` | `create_app` |
| Stylesheets declare `@layer components`, scope every selector to `[data-app="{key}"]`, and use no colour literals, `--p-*` tokens or `!important` | `create_app` |
| Help topics have front matter, and links and the page map point to real topics | `create_app` |
| Every list of records is a `GridSpec` | Review |
| Every page has a `NavNode` and renders with `render_page` | Review |
| Status values get their labels and tones from their grid `Column` | Review |
| Every router that changes data has `Depends(csrf_protect)` | Review and tests |
| Feedback is a toast, never `alert()` or a banner | Review |

## The parts

| Page | Covers |
|---|---|
| [Pages and navigation](pages-and-navigation.md) | `NavNode`, `render_page`, page types, detail pages, breadcrumbs |
| [Grids](grids.md) | `GridSpec` in depth: columns, filters, views, actions, panels, layouts, embedding |
| [Forms and feedback](forms-and-feedback.md) | Form posts, validation, CSRF, toasts and flash messages |
| [UI components](ui-components.md) | Macros, buttons, tones, icons, keyboard and accessibility |
| [Styling](styling.md) | The five CSS layers, tokens, light and dark, an app's own stylesheet |
| [Data and audit](data-and-audit.md) | Models, migrations, timestamps, the audit log, seed data, background work |
| [Access control](access-control.md) | Roles, `require_roles`, row scoping and what the server checks |
| [Ctrl+J search](search.md) | Making pages and records findable, custom sources, commands |
| [Writing help](writing-help.md) | Help topics, sections, callouts, diagrams and the F1 map |
| [Testing](testing.md) | The fixtures, what to test and how |

## Working examples

The demo app in `apps/demo/lattice_demo/` uses every part:

| File | Shows |
|---|---|
| `work_items.py` | A table grid with views, filters, bulk actions with input fields, a side panel, a detail page, create and edit forms, home tiles and Ctrl+J |
| `jobs.py` | A grid that refreshes itself, actions that depend on each row's state, and a background task |
| `inbox.py` | A split list with a reading pane, rows scoped to the signed-in user, and a star toggle |
| `templates/demo/` | A detail page, panels and a form built from the shared macros |
| `static/demo.css` | An app stylesheet scoped to `[data-app="demo"]` |
| `help/` | Help topics with a Mermaid diagram, a callout and a `help.toml` |
