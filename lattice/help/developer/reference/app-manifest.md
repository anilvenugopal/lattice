---
title: App manifest
summary: AppManifest and the records it holds: NavNode, HomeTile, SearchProvider.
order: 20
keywords: manifest navnode navigation tile provider
---

> [!NOTE]
> Generated from `lattice/components/manifest.py`, `lattice/kernel/nav/manifest.py`, `lattice/components/tiles.py` and `lattice/components/search/providers.py` by `lattice docs build`. Change the code, not this page.

An app is a package that exports one `AppManifest` as `APP`. A host lists the apps it runs in `create_app(apps=[…])`, which checks every rule below before the host starts.

## AppManifest

What an app adds to a host. Listed once per app package.

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | URL prefix /{key}, grid key prefix {key}. |
| `label` | `str` | required | app name in menus, Help and Ctrl+J |
| `icon` | `str` | `''` | icon registry name, e.g. "showcase:app" |
| `help_url` | `str` | `''` | listed in the shell's Help menu |
| `nav` | `list[NavNode]` | `[]` | the app's pages; every page has a node |
| `routers` | `list[APIRouter]` | `[]` | FastAPI routers, mounted as declared (paths start with /{key}) |
| `grids` | `list[GridSpec]` | `[]` | registered for actions, export, Ctrl+J and tiles |
| `charts` | `list[ChartSpec]` | `[]` | served at /_chart/{key}/data |
| `forms` | `list[FormSpec]` | `[]` | JSON Schema forms: /_form/{key}/render |
| `schemas` | `list[SchemaDef]` | `[]` | named schemas forms can apply |
| `documents` | `list[DocumentKind]` | `[]` | kinds in the document store |
| `search` | `list[SearchProvider]` | `[]` | extra Ctrl+J sources |
| `tiles` | `list[HomeTile]` | `[]` | count tiles on the home page |
| `templates` | `Path \| None` | `None` | Folder holding templates/{key}/…; searched before core templates. |
| `static` | `Path \| None` | `None` | Folder served at /static/{key}/, and stylesheets in it loaded on every page. Each stylesheet declares @layer components and scopes every selector to [data-app="{key}"] (ADR 0010). |
| `stylesheets` | `list[str]` | `[]` | file names inside `static` |
| `icons` | `dict[str, str]` | `{}` | Icons the app adds, used as icon("{key}:name"). Values are SVG path markup. |
| `permissions` | `list[Permission]` | `[]` | What the app's users may do: checked with require(), permission=, can(). |
| `sql` | `Path \| None` | `None` | Folder of the app's SQL: named queries in *.sql, migrations in schema/*.sql. The migrations create and fill the Postgres schema named after the app's key. |
| `help` | `Path \| None` | `None` | Folder of Markdown help topics with index.md and an optional help.toml page map. |
| `slots` | `dict[str, str]` | `{}` | Slot name -> template in the app's own folder ("{key}/…"). |
| `background` | `Callable[[], Awaitable[None]] \| None` | `None` | Started with the host, cancelled at shutdown. |
| `seed` | `Callable[[Db], None] \| None` | `None` | Development data for `lattice seed`; receives a Db in the seed's transaction. |

## NavNode

A page in the navigation. Top-level nodes are rail icons; their children are the sidebar.

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | unique; pages pass it to render_page |
| `label` | `str` | required | menu text and page title |
| `route` | `str` | required | URL of the page |
| `parent` | `str \| None` | `None` | key of the parent node; None for a rail icon |
| `icon` | `str \| None` | `None` | rail icon name, see lattice/kernel/icons.py |
| `permission` | `str` | `''` | who may open it; empty = every signed-in user |
| `hidden` | `bool` | `False` | routing/breadcrumb only |
| `bottom` | `bool` | `False` | rail bottom group |
| `keywords` | `str` | `''` | extra Ctrl+J match terms |
| `description` | `str` | `''` | shown under the page in Ctrl+J results |
| `app` | `str` | `''` | owning app key, set when registered |

## HomeTile

A count on the home page: the rows of a grid view, linking to that view.

| Field | Type | Default | Description |
|---|---|---|---|
| `label` | `str` | required | tile text |
| `spec` | `GridSpec` | required | the grid whose rows are counted |
| `view` | `str` | `''` | key of one of the grid's views |
| `filters` | `dict[str, list[str]]` | `{}` | extra filters: column -> values |
| `tone` | `str` | `''` | stat tone, shown only when the count is above zero |

## SearchProvider

A Ctrl+J source: answers a query and renders a preview of one result.

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | unique; the filter chip and the preview URL use it |
| `label` | `str` | required | filter chip text |
| `icon` | `str` | required | icon shown on its results |
| `search` | `Callable[[Db, object, str, int], list[SearchResult]]` | required | (db, user, query, limit) -> results |
| `count` | `Callable[[Db, object, str], int]` | required | (db, user, query) -> number of matches, for the filter chip |
| `preview` | `Callable[[Request, Db, str], object]` | required | (request, db, result id) -> HTML for the preview pane |
| `permission` | `str` | `''` | who sees the source; empty = every signed-in user |

## SearchResult

One Ctrl+J result.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | `str` | required | passed back to the provider's preview |
| `title` | `str` | required | result text |
| `subtitle` | `str` | `''` | muted second line |
| `href` | `str` | `''` | opened with Enter; empty for commands |
| `command` | `str` | `''` | key of a client-side command (static/js/palette.js) |
