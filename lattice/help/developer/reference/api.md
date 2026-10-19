---
title: Python API
summary: Every name in lattice.api, the only module an app imports.
order: 10
keywords: import public api lattice.api
---

> [!NOTE]
> Generated from `lattice/api.py` by `lattice docs build`. Change the code, not this page.

The public API of Lattice: the only module an app may import (ADR 0002).

```python
from lattice.api import AppManifest, GridSpec, render_page
```

## Apps and navigation

| Name | Kind | Description |
|---|---|---|
| [`AppManifest`](app-manifest.md#appmanifest) | class | What an app adds to a host. Listed once per app package. |
| [`NavNode`](app-manifest.md#navnode) | class | A page in the navigation. Top-level nodes are rail icons; their children are the sidebar. |
| [`HomeTile`](app-manifest.md#hometile) | class | A count on the home page: the rows of a grid view, linking to that view. |
| [`SearchProvider`](app-manifest.md#searchprovider) | class | A Ctrl+J source: answers a query and renders a preview of one result. |
| [`SearchResult`](app-manifest.md#searchresult) | class | One Ctrl+J result. |

## Grid

| Name | Kind | Description |
|---|---|---|
| [`Action`](grid.md#action) | class | A button in the grid's action bar and row menu. |
| [`ActionContext`](grid.md#actioncontext) | class | What an action handler receives. |
| [`ActionResult`](grid.md#actionresult) | class | What an action handler may return. A plain string is the success message. |
| [`Column`](grid.md#column) | class | A column of the grid. Its `labels` and `tones` are the one place a status value's text and colour are declared. |
| [`Field`](grid.md#field) | class | An input collected in a dialog before an action runs. |
| [`Filter`](grid.md#filter) | class | A dropdown in the filter bar that narrows rows to the chosen values of one column. |
| [`GridSpec`](grid.md#gridspec) | class | One list screen: what rows exist, how they look, how users narrow them and what they can do with a selection. |
| [`Palette`](grid.md#palette) | class | Makes rows findable from Ctrl+J (one search provider per grid, see lattice/components/search/providers.py). |
| [`View`](grid.md#view) | class | A named preset of filters shown as a tab above the grid (or in the sidebar). |
| `build_grid` `(request, db, spec, views_in_nav=False, sync_url=True, fixed=None)` | function | Template context for components/grid.html: render it with `data_grid(grid)`. |
| `render_grid_page` `(request, db, spec, nav_key, title='', subtitle='', views_in_nav=False)` | function | A full page holding one grid: the standard list screen. |

## Record pages

| Name | Kind | Description |
|---|---|---|
| `RecordPage` | class | One record of a grid as a full page: header, properties, panels and history. |
| `Panel` | class | A section of the record page, drawn by the app's own template. |
| `Link` | class | A header button that opens a page, e.g. the record's edit form. |
| `render_record_page` `(request, db, page, record_id, **extra)` | function | The record page for one row. Extra keyword arguments reach the panel templates. |

## Charts

| Name | Kind | Description |
|---|---|---|
| `ChartSpec` | class | One chart over a grid's rows. |
| `Count` | class | Rows per group. |
| `Sum` | class |  |
| `Avg` | class |  |
| `Min` | class |  |
| `Max` | class |  |
| `Time` | class | A time dimension: the column truncated to `unit` (Postgres date_trunc). |
| `Threshold` | class | A horizontal line across a bar, line or area chart, e.g. a target or a limit. |
| `build_chart` `(request, chart, linked=True, fixed=None)` | function | Context for one chart on a page. |

## Forms from JSON Schema

| Name | Kind | Description |
|---|---|---|
| `FormSpec` | class | A form drawn from a JSON Schema. JSON in, JSON out; the app loads and saves. |
| `SchemaDef` | class | A named JSON Schema that forms can apply, e.g. a document kind's schema. |
| `FormResult` | class |  |
| `build_form` `(request, spec, data, errors=None, general=None, schema_id='', mode='form', chosen=None, json_text=None)` | function | Context for components/json_form.html: render it with `json_form(form, …)`. |
| `parse_form` `(request, spec, form)` | function | Read a posted form back into a document and validate it against the schema in force. |
| `DocumentKind` | class |  |
| `InvalidDocument` | class | The data does not satisfy the kind's schema. |
| `documents` | module | The document store (ADR 0007): JSON documents of kinds that apps declare. |

## Pages and feedback

| Name | Kind | Description |
|---|---|---|
| `render` `(request, template, status_code=200, headers=None, **ctx)` | function | Render a template; context goes in as keyword arguments, as for render_page(). |
| `render_page` `(request, template, nav_key, status_code=200, **ctx)` | function | Render a page inside the shell. `nav_key` is a NavNode key from lattice/kernel/nav/manifest.py. |
| `flash` `(response, request, message, tone='success')` | function | Show `message` as a toast on the next full page load (use with a redirect after a form post). |
| `toast` `(message, tone='success', **events)` | function | Response headers that show a toast (and fire extra HTMX events) on the client. |

## Requests and access

| Name | Kind | Description |
|---|---|---|
| `csrf_protect` `(request)` | function | Router dependency. Raises 403 when an unsafe request lacks the matching token. |
| `current_user` `(request)` | function | Route dependency: the signed-in user (401 when nobody is signed in). |
| `require` `(permission)` | function | Route dependency: 403 unless the user has `permission`. |
| `Permission` | class |  |

## Data

| Name | Kind | Description |
|---|---|---|
| `Db` | class | Runs named queries on one connection, inside its transaction. |
| `get_db` `()` | function | Route dependency: the request's `Db`, in one transaction for the whole request. |
| `transaction` `()` | function | A `Db` in its own transaction: committed on success, rolled back on an exception. |
| `NotFound` | class | `Db.one` found no row. Routes turn it into a 404. |
| `Query` | class |  |
| `sql_queries` `(folder)` | function | Load every `*.sql` file in `folder` (not its `schema/` migrations). Loaded once. |
| `audit` | module | Audit trail. |
| `users` | module | User lookup and creation. Every caller (admin UI, SSO, scripts, tests) goes through here. |
| [`settings`](settings.md) | value | The running configuration, read from `LATTICE_*` environment variables. |

## Development data

| Name | Kind | Description |
|---|---|---|
| `DEV_USERS` | value | (email, name, password, roles) of the development accounts `lattice seed` creates; app tests sign in as them. |
