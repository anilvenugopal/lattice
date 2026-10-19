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
    sql/schema/0001_helpdesk.sql  migrations: the app's tables, in schema "helpdesk"
    sql/tickets.sql               named SQL queries, one file per area
    tickets.py                    one module per area: GridSpec, actions, routes
    seed.py                       example data for `lattice seed` (optional)
    templates/helpdesk/           Jinja templates, only in a folder named after the key
    static/helpdesk.css           styles scoped to [data-app="helpdesk"] (optional)
    help/                         Markdown topics and help.toml
  tests/
    conftest.py                   host_apps fixture returning [APP]
    sql/checks.sql                named queries the tests use
    test_tickets.py
```

## The rules

`create_app` and the tests enforce most of these; reviews catch the rest.

| Rule | Enforced by |
|---|---|
| Import only `lattice.api`, never another app, SQLAlchemy or psycopg | `make lint` (import contracts) |
| The key is lowercase letters, digits and underscores, and not reserved | `create_app` |
| Nav routes and grid paths start with `/{key}`; grid keys start with `{key}.` | `create_app` |
| Templates only in `templates/{key}/`; slot templates in `{key}/` | `create_app` |
| Stylesheets declare `@layer components`, scope every selector to `[data-app="{key}"]`, and use no colour literals, `--p-*` tokens or `!important` | `create_app` |
| Help topics have front matter, and links and the page map point to real topics | `create_app` |
| Tables only in `sql/schema/` migrations, in the schema named after the key | Review |
| Every SQL statement is a named query in `sql/*.sql`, with a comment; no SQL in Python, no ORM | `make test` (SQL rules), `make lint` |
| Every named query is used, and valid SQL | `make test` (SQL rules) |
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
| [Charts](charts.md) | `ChartSpec`: bar, line, area, pie, calendar, treemap, sankey and map charts on a grid's rows, linked to its filters |
| [Record pages](record-pages.md) | `RecordPage`: the standard detail page for one grid row, with its actions, panels and history |
| [Grid performance](grid-performance.md) | What the database runs for a grid, what is expensive on large tables, and how to keep grids fast |
| [Forms from JSON Schema](json-forms.md) | `FormSpec`: a form drawn from a Pydantic model or JSON Schema, JSON in and out; the document store |
| [Flows](flows.md) | Stepper, tree and graph: steps of a process, hierarchies, and DAGs with node actions |
| [Forms and feedback](forms-and-feedback.md) | Form posts, validation, CSRF, toasts and flash messages |
| [UI components](ui-components.md) | Macros, buttons, tones, icons, keyboard and accessibility |
| [Styling](styling.md) | The five CSS layers, tokens, light and dark, an app's own stylesheet |
| [Data and audit](data-and-audit.md) | Tables and migrations, named SQL queries, `Db` and transactions, the audit log, seed data, background work |
| [Access control](access-control.md) | Users, roles and permissions; `require`, `permission=` and `can`; row scoping and what the server checks |
| [Working across apps](working-across-apps.md) | References as URNs, panels on other apps' record pages, and CloudEvents |
| [Ctrl+J search](search.md) | Making pages and records findable, custom sources, commands |
| [Writing help](writing-help.md) | Help topics, sections, callouts, diagrams and the F1 map |
| [Testing](testing.md) | The fixtures, what to test and how |

## Working examples

The showcase in `apps/showcase/lattice_showcase/` uses every part:

| File | Shows |
|---|---|
| `items.py` | A table grid with every column kind, views, filters, bulk actions with input fields, a star toggle, a side panel, the record page, create and edit forms, home tiles and Ctrl+J |
| `jobs.py` | A grid that refreshes itself, actions that depend on each row's state, and a background task |
| `inbox.py` | A split list with a reading pane, rows scoped to the signed-in user, and a star toggle |
| `charts.py` | Ten charts on the Items grid, linked to its filters |
| `specs.py` | Forms from a Pydantic model, the document store, and a form with no schema |
| `flows.py` | A stepper, a tree and a dependency graph with node actions |
| `templates/showcase/` | Record page panels, the overview, and a form built from the shared macros |
| `static/showcase.css` | An app stylesheet scoped to `[data-app="showcase"]` |
| `help/` | Help topics with a Mermaid diagram, a callout and a `help.toml` |
