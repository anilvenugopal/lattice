---
title: Grid
summary: GridSpec and the classes that describe columns, filters, views and actions.
order: 30
keywords: gridspec column action filter view table list
---

> [!NOTE]
> Generated from `lattice/components/grid/spec.py` by `lattice docs build`. Change the code, not this page.

Declarative grid definition. One GridSpec per list screen.

**Column kinds:** `text`, `strong`, `mono`, `number`, `money`, `percent`, `date`, `datetime`, `ago`, `badge`, `bool`, `tags`, `progress`, `user`, `star`, `template`.

**Tones:** `neutral`, `info`, `success`, `warning`, `danger`, `accent`.

## GridSpec

One list screen: what rows exist, how they look, how users narrow them and what they can do
with a selection.

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | unique: "{app}.{name}" |
| `title` | `str` | required | heading and Ctrl+J source name |
| `path` | `str` | required | page that hosts the grid |
| `query` | `Query` | required | A named query (sql/<area>.sql) returning the rows, with an "id" column. It may use :user_id (the signed-in user) to scope rows. |
| `columns` | `list[Column]` | required | in display order |
| `params` | `dict[str, Any]` | `{}` | Fixed values the query is run with, beside :user_id, e.g. {"kind": "showcase.spec"}. Part of the access boundary: users cannot change them. |
| `search` | `list[str]` | `[]` | columns matched by the search box (ILIKE) |
| `filters` | `list[Filter]` | `[]` | dropdowns in the filter bar |
| `views` | `list[View]` | `[]` | tabs of preset filters |
| `actions` | `list[Action]` | `[]` | buttons in the action bar and row menu |
| `selection` | `Literal['multi', 'single', 'none']` | `'multi'` | how many rows can be selected |
| `default_sort` | `str` | `'-id'` | "-" prefix sorts descending |
| `row_href` | `str` | `''` | Enter / double-click target |
| `panel` | `Callable[[Db, Any, dict], dict] \| None` | `None` | (db, user, row) -> context for the side panel; None: no panel |
| `panel_title` | `str` | `'{id}'` | side panel heading, formatted with the row |
| `layout` | `Literal['table', 'split']` | `'table'` | split: list + reading pane |
| `row_class` | `Callable[[dict], str] \| None` | `None` | extra CSS class per row, e.g. unread |
| `poll_seconds` | `int` | `0` | reload rows every n seconds; 0 = never |
| `export` | `bool` | `True` | offer CSV download of the filtered rows |
| `permission` | `str` | `''` | who may open the grid; empty = every signed-in user |
| `search_placeholder` | `str` | `'Search'` | search box hint |
| `empty_title` | `str` | `'Nothing here yet'` | shown when no rows match |
| `empty_text` | `str` | `''` | second line under empty_title |
| `palette` | `Palette \| None` | `None` | make rows findable from Ctrl+J |
| `spatial` | `tuple[str, str] \| None` | `None` | (lon, lat) columns: rows can then be narrowed to a shape drawn on a linked map. The shape travels in the URL like a filter. Needs PostGIS (ADR 0013). |

## Column

A column of the grid. Its `labels` and `tones` are the one place a status value's text and
colour are declared.

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | label of a column in GridSpec.query |
| `label` | `str` | required | header text |
| `kind` | `ColumnKind` | `'text'` | how values render, see Column kinds |
| `sortable` | `bool` | `True` | header click sorts by it |
| `hidden` | `bool` | `False` | off until the user turns it on in the Columns menu |
| `required` | `bool` | `False` | cannot be turned off |
| `width` | `str` | `''` | CSS width, e.g. "120px" |
| `align` | `Literal['', 'right', 'center']` | `''` | header and cell alignment |
| `tones` | `dict[str, Tone]` | `{}` | badge: value -> tone |
| `labels` | `dict[str, str]` | `{}` | value -> display text |
| `href` | `str` | `''` | link target, formatted with the row: "/work/{id}" |
| `secondary` | `str` | `''` | key shown as a muted second line |
| `template` | `str` | `''` | kind="template": partial rendered with `row`, `col` |
| `star_action` | `str` | `''` | kind="star": action key toggled by clicking the star |

## Filter

A dropdown in the filter bar that narrows rows to the chosen values of one column.

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | column label in GridSpec.query |
| `label` | `str` | required | dropdown text |
| `options` | `Options` | required | (value, label) pairs, or a function (db, user) returning them |
| `multiple` | `bool` | `True` | allow several values (matched with IN) |

## View

A named preset of filters shown as a tab above the grid (or in the sidebar).

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | in the URL as ?view= |
| `label` | `str` | required | tab text |
| `where` | `dict[str, Any]` | `{}` | "$me" means the current user id |
| `sort` | `str` | `''` | sort applied with the view, e.g. "-created_at" |

## Action

A button in the grid's action bar and row menu.

# selection it needs, see above
scope: "none" needs no selection (e.g. New), "single" exactly one row,
"multi" one or more rows.
Either `handler` runs server-side, or `href` navigates ("/work/{id}" for single).
`when` restricts eligible rows, e.g. {"status": ["failed"]}: the button is
disabled unless at least one selected row matches, and the server drops rows
that do not match before calling the handler (the toast reports them as
skipped). `when` keys must hold plain JSON values (str, int, bool, None).
The handler runs in the request's transaction, with the grid's audit events; if it
raises, nothing is saved.

| Field | Type | Default | Description |
|---|---|---|---|
| `key` | `str` | required | unique in the grid; the audit event is "{grid key}.{action key}" |
| `label` | `str` | required | button text |
| `scope` | `Literal['none', 'single', 'multi']` | `'multi'` | selection it needs, see above |
| `handler` | `ActionHandler \| None` | `None` | runs server-side with an ActionContext |
| `href` | `str` | `''` | navigate instead of running a handler |
| `confirm` | `str` | `''` | "{count}" is replaced with the selection size |
| `tone` | `Literal['default', 'primary', 'danger']` | `'default'` | button style |
| `icon` | `str` | `''` | icon name, see Slots and icons |
| `permission` | `str` | `''` | who may run it; empty = every user who can see the grid |
| `fields` | `list[Field]` | `[]` | inputs asked for in a dialog before the action runs |
| `when` | `dict[str, list[Any]]` | `{}` | row values the action applies to, e.g. {"status": ["failed"]} |
| `in_row_menu` | `bool` | `True` | also list the action in each row's ⋯ menu |

## Field

An input collected in a dialog before an action runs.

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | required | key in ActionContext.values |
| `label` | `str` | required | input label |
| `kind` | `Literal['text', 'textarea', 'select', 'number', 'date']` | `'text'` | input type |
| `options` | `Options` | `[]` | kind="select": (value, label) pairs or a function (db, user) |
| `required` | `bool` | `False` | the dialog will not submit without it |
| `default` | `str` | `''` | initial value |
| `placeholder` | `str` | `''` | hint inside the empty input |

## ActionContext

What an action handler receives.

| Field | Type | Default | Description |
|---|---|---|---|
| `db` | `Db` | required | the request's Db, in the request's transaction |
| `user` | `Any` | required | CurrentUser |
| `ids` | `list[Any]` | required | eligible ids, already scoped by GridSpec.query |
| `rows` | `list[dict]` | required | the eligible rows as the grid query returns them |
| `values` | `dict[str, str]` | required | Field inputs |
| `query` | `Any` | `None` | The grid's state when the action ran: search, filters, view, fixed filters and a drawn shape (query.shape), e.g. for a toolbar action that saves what the user narrowed to. |

## ActionResult

What an action handler may return. A plain string is the success message.

| Field | Type | Default | Description |
|---|---|---|---|
| `message` | `str` | `''` | toast text; default "{action label}: {n} updated." |
| `tone` | `Tone` | `'success'` | toast tone |
| `refresh` | `bool` | `True` | reload the grid rows |
| `clear_selection` | `bool` | `True` | empty the selection after |
| `redirect` | `str` | `''` | navigate to this URL instead of refreshing |

## Palette

Makes rows findable from Ctrl+J (one search provider per grid, see lattice/components/search/providers.py).

Strings are formatted with the row; `href` values are URL-encoded.

| Field | Type | Default | Description |
|---|---|---|---|
| `title` | `str` | required | result title, formatted with the row: "{ref} · {title}" |
| `href` | `str` | required | opened with Enter: "/showcase/items/{id}" |
| `subtitle` | `str` | `''` | muted second line |
| `icon` | `str` | `'link'` | result icon |
