"""Ctrl+J search providers.

A provider answers a query with results and renders a preview for one result.
Built in: Pages (nav manifest), one provider per GridSpec with `palette=`, and
Commands. Add another source with register_provider().

The palette (components/palette_body.html, static/js/palette.js) shows provider
filters with counts, the results, and a preview of the highlighted result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from lattice.components.grid import REGISTRY, GridSpec, engine
from lattice.components.grid.render import render_panel
from lattice.kernel.nav import NODES, search_nodes
from lattice.kernel.nav.manifest import BY_KEY
from lattice.kernel.web import fmt, fmt_url, render


@dataclass(frozen=True)
class SearchResult:
    id: str
    title: str
    subtitle: str = ""
    href: str = ""          # opened with Enter; empty for commands
    command: str = ""       # key of a client-side command (static/js/palette.js)


@dataclass(frozen=True)
class SearchProvider:
    key: str
    label: str
    icon: str
    search: Callable[[Session, object, str, int], list[SearchResult]]
    count: Callable[[Session, object, str], int]
    preview: Callable[[Request, Session, str], object]
    roles: tuple[str, ...] = field(default=())


# ── Pages ────────────────────────────────────────────────────────────────────

def _visible_pages(user, q: str):
    if q:
        return search_nodes(user, q)
    return [n for n in NODES if not n.hidden and user.has_any(n.roles)]


def _page_result(node) -> SearchResult:
    parent = BY_KEY[node.parent].label if node.parent else ""
    return SearchResult(id=node.key, title=node.label,
                        subtitle=" › ".join(p for p in (parent, node.description) if p),
                        href=node.route)


def _page_preview(request: Request, db: Session, key: str):
    node = BY_KEY.get(key)
    user = request.state.user
    if node is None or node.hidden or not user.has_any(node.roles):
        raise HTTPException(404)
    chain = [node]
    while chain[0].parent:
        chain.insert(0, BY_KEY[chain[0].parent])
    children = [n for n in NODES if n.parent == key and not n.hidden and user.has_any(n.roles)]
    return render(request, "components/search_preview_page.html", node=node, chain=chain,
                  children=children)


PAGES = SearchProvider(
    key="pages", label="Pages", icon="layout",
    search=lambda db, user, q, limit: [_page_result(n) for n in _visible_pages(user, q)[:limit]],
    count=lambda db, user, q: len(_visible_pages(user, q)),
    preview=_page_preview,
)


# ── Commands ─────────────────────────────────────────────────────────────────
# key, label, what it does. Each key has a handler in static/js/palette.js.

COMMANDS = [
    ("theme-light", "Theme: Light", "Switch to the light theme and remember it."),
    ("theme-dark", "Theme: Dark", "Switch to the dark theme and remember it."),
    ("theme-system", "Theme: Match system", "Follow the operating system's light or dark setting."),
    ("preferences", "Open preferences", "Theme, density, page size, start page and time format."),
    ("shortcuts", "Show keyboard shortcuts", "Every keyboard shortcut in the app."),
    ("signout", "Sign out", "End this session and return to the sign-in page."),
]


def _matching_commands(q: str):
    words = q.lower().split()
    return [c for c in COMMANDS if all(w in f"{c[1]} {c[2]}".lower() for w in words)]


def _command_preview(request: Request, db: Session, key: str):
    command = next((c for c in COMMANDS if c[0] == key), None)
    if command is None:
        raise HTTPException(404)
    return render(request, "components/search_preview_command.html", label=command[1],
                  description=command[2])


COMMANDS_PROVIDER = SearchProvider(
    key="commands", label="Commands", icon="keyboard",
    search=lambda db, user, q, limit: [SearchResult(id=k, title=label, subtitle=desc, command=k)
                                       for k, label, desc in _matching_commands(q)[:limit]],
    count=lambda db, user, q: len(_matching_commands(q)),
    preview=_command_preview,
)


# ── Grids ────────────────────────────────────────────────────────────────────

def grid_provider(spec: GridSpec) -> SearchProvider:
    """Records of a grid that declares `palette=`. Empty queries return no records."""
    def search(db, user, q, limit):
        if not q:
            return []
        rows = engine.fetch_all(spec, db, user, engine.GridQuery(q=q), limit)
        return [SearchResult(id=str(r["id"]), title=fmt(spec.palette.title, r),
                             subtitle=fmt(spec.palette.subtitle, r),
                             href=fmt_url(spec.palette.href, r)) for r in rows]

    return SearchProvider(
        key=f"grid.{spec.key}", label=spec.title, icon=spec.palette.icon, roles=spec.roles,
        search=search,
        count=lambda db, user, q: engine.count(spec, db, user, engine.GridQuery(q=q)) if q else 0,
        preview=lambda request, db, row_id: render_panel(request, db, spec, row_id, preview=True),
    )


# ── Registry ─────────────────────────────────────────────────────────────────

_EXTRA: list[SearchProvider] = []


def reset() -> None:
    _EXTRA.clear()


def register_provider(provider: SearchProvider) -> SearchProvider:
    """Add a search source (e.g. an external system) after the grid providers."""
    _EXTRA.append(provider)
    return provider


def providers_for(user) -> list[SearchProvider]:
    """Pages, then grids in navigation order, then registered providers, then Commands."""
    rank = {node.route: i for i, node in reversed(list(enumerate(NODES)))}
    grids = sorted((s for s in REGISTRY.values() if s.palette),
                   key=lambda s: rank.get(s.path, len(rank)))
    all_providers = [PAGES, *map(grid_provider, grids), *_EXTRA, COMMANDS_PROVIDER]
    return [p for p in all_providers if user.has_any(p.roles)]


def provider_for(user, key: str) -> SearchProvider:
    provider = next((p for p in providers_for(user) if p.key == key), None)
    if provider is None:
        raise HTTPException(404)
    return provider
