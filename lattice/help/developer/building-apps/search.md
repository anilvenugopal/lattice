---
title: Ctrl+J search
summary: Make an app's pages and records findable from Ctrl+J, add a source of your own, and add commands.
order: 80
keywords: ctrl+j ctrl j palette search jump provider source preview command palette
---

Ctrl+J is the one place a user goes to find anything: a page, a record, a help
topic or a command. It has three columns:

- **Sources** on the left: All, then each source with its count of matches.
- **Results** in the middle: five per source under All, up to 30 for one
  source.
- **Preview** on the right: the highlighted result.

| Keys | Do |
|---|---|
| ↑ ↓ | Move the highlight; the preview follows |
| Tab, Shift+Tab | Next or previous source |
| Enter | Open the result, or run the command |
| Esc | Close |

The sources appear in this order:

1. Pages.
2. One source per grid with `palette=`, in navigation order.
3. Sources that apps add, then Help.
4. Commands.

Each source is shown only to users who hold its roles.

## Pages

Every visible `NavNode` the user may open is a result. Help users find pages
with words they would type:

```python
NavNode("tickets", "Tickets", "/helpdesk/tickets", icon="inbox",
        keywords="cases requests support issues",
        description="Customer tickets, from opening to close")
```

`keywords` are matched but not shown. `description` is shown under the result
and in the preview.

## Records

Give a grid a `Palette` and its rows become a source:

```python
GRID = GridSpec(
    key="helpdesk.tickets", title="Tickets", …,
    search=["ref", "subject", "assignee"],
    palette=Palette(title="{ref} · {subject}", subtitle="{assignee}",
                    href="/helpdesk/tickets/{id}", icon="inbox"),
)
```

- **Matching.** The query text is matched like the grid's search box: across
  the `search` columns, every word must match.
- **Labels.** The source is named after the grid's `title`.
- **Text and link.** `title`, `subtitle` and `href` are filled from each row.
  Values put into `href` are URL-encoded.
- **Preview.** The preview is the grid's side panel, read-only, with an Open
  button.
- **Access.** Results come through the grid's query and roles, so users find
  only rows they could see in the list.

## A source of your own

For anything that is not a grid, such as records in an external system, add a
`SearchProvider` to the manifest's `search`:

```python
from fastapi import HTTPException, Request

from lattice.api import SearchProvider, SearchResult, render


def _search(db, user, q: str, limit: int) -> list[SearchResult]:
    if not q:
        return []
    return [SearchResult(id=str(a.id), title=a.name, subtitle=a.region,
                         href=f"/helpdesk/accounts/{a.id}")
            for a in crm.find_accounts(q, limit=limit)]


def _count(db, user, q: str) -> int:
    return crm.count_accounts(q) if q else 0


def _preview(request: Request, db, item_id: str):
    account = crm.get_account(item_id)
    if account is None:
        raise HTTPException(404)
    return render(request, "helpdesk/account_preview.html", account=account)


ACCOUNTS = SearchProvider(key="helpdesk.accounts", label="CRM accounts", icon="users",
                          search=_search, count=_count, preview=_preview)

APP = AppManifest(key="helpdesk", …, search=[ACCOUNTS])
```

| Function | Receives | Returns |
|---|---|---|
| `search` | `(db, user, query, limit)` | Up to `limit` `SearchResult`s. Return none for an empty query |
| `count` | `(db, user, query)` | The number of matches, for the source's count |
| `preview` | `(request, db, result id)` | The preview pane's HTML, rendered with `render`. 404 if the user may not see it |

`search` and `count` run on every keystroke (debounced), once per source, so
keep them fast. Check access in all three functions; `permission=` on the provider
hides the whole source.

## Commands

Commands are actions that are not about one record, such as "Theme: Dark" or
"Sign out". Today they are defined in Lattice:

1. Add a `(key, label, description)` row to `COMMANDS` in
   `lattice/components/search/providers.py`.
2. Handle the key in `runCommand()` in `lattice/static/js/palette.js`.

Apps cannot add commands yet.
