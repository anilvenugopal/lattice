"""Navigation: NavNode and the registry of every app's nodes.

Each app declares its nodes in its AppManifest; create_app registers them here.
Rail, sidebar, breadcrumbs, page titles, role gating of menus and the Ctrl+J
pages all derive from NODES. Adding a page = one NavNode + one route.

A route passes its node key to `render_page(..., nav_key=...)`.
Top-level nodes (parent=None) are rail icons. Their children are the sidebar.
`hidden=True` nodes (detail pages) never show in menus but still resolve
breadcrumbs and keep their parent highlighted.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class NavNode:
    """A page in the navigation. Top-level nodes are rail icons; their children are the sidebar."""

    key: str                        # unique; pages pass it to render_page
    label: str                      # menu text and page title
    route: str                      # URL of the page
    parent: str | None = None       # key of the parent node; None for a rail icon
    icon: str | None = None          # rail icon name, see lattice/kernel/icons.py
    permission: str = ""             # who may open it; empty = every signed-in user
    hidden: bool = False             # routing/breadcrumb only
    bottom: bool = False             # rail bottom group
    keywords: str = ""               # extra Ctrl+J match terms
    description: str = ""           # shown under the page in Ctrl+J results
    app: str = ""                    # owning app key, set when registered


# Filled by lattice.host.create_app from the app manifests, in rail order.
NODES: list[NavNode] = []
BY_KEY: dict[str, NavNode] = {}
# Each app's accent tone (AppManifest.accent, ADR 0010): its rail entry and page headers.
ACCENTS: dict[str, str] = {}


def reset() -> None:
    NODES.clear()
    BY_KEY.clear()
    ACCENTS.clear()


def add(nodes: list[NavNode], app_key: str) -> None:
    """Register an app's nodes, tagged with the app that owns them.

    Lattice's own platform apps pass app_key "", so their pages carry no data-app.
    """
    for node in nodes:
        if node.key in BY_KEY:
            raise ValueError(f"Nav key {node.key!r} is declared twice "
                             f"(apps {BY_KEY[node.key].app!r} and {app_key!r})")
        node = replace(node, app=app_key)
        NODES.append(node)
        BY_KEY[node.key] = node


def _chain(key: str) -> list[NavNode]:
    node = BY_KEY[key]
    chain = [node]
    while node.parent:
        node = BY_KEY[node.parent]
        chain.insert(0, node)
    return chain


def _pages(node: NavNode, user=None) -> list[NavNode]:
    """A section's menu pages, those `user` may open when given."""
    return [n for n in NODES if n.parent == node.key and not n.hidden
            and (user is None or user.can(n.permission))]


def can_open(user, node: NavNode) -> bool:
    """The user has the node's permission and, for a section, may open one of its pages."""
    return user.can(node.permission) and (not _pages(node) or bool(_pages(node, user)))


def _entry(user, node: NavNode) -> NavNode:
    """A rail icon leads to the first page of its section the user may open."""
    pages = _pages(node, user)
    return replace(node, route=pages[0].route) if pages else node


def nav_context(user, active_key: str) -> dict:
    """Everything base/shell.html needs to draw rail, sidebar and breadcrumb."""
    chain = _chain(active_key)
    section = chain[0]
    visible = [n for n in NODES if can_open(user, n)]
    sidebar = [n for n in visible if n.parent == section.key and not n.hidden]
    # The highlighted sidebar entry is the nearest visible ancestor of the active node.
    sidebar_keys = {n.key for n in sidebar}
    active_item = next((n.key for n in reversed(chain) if n.key in sidebar_keys), None)
    return {
        "rail": [_entry(user, n) for n in visible
                 if n.parent is None and not n.bottom and not n.hidden],
        "rail_bottom": [_entry(user, n) for n in visible
                        if n.parent is None and n.bottom and not n.hidden],
        "section": section,
        "sidebar": sidebar,
        "active_key": active_key,
        "active_item": active_item,
        "breadcrumb": [_entry(user, chain[0]), *chain[1:]],
        "title": chain[-1].label,
        "app": chain[-1].app,                       # <main data-app="…"> (ADR 0010)
        "accent": ACCENTS.get(chain[-1].app, ""),
        "accents": ACCENTS,
    }


def search_nodes(user, q: str) -> list[NavNode]:
    q = q.lower().strip()
    hits = []
    for n in NODES:
        if n.hidden or not can_open(user, n):
            continue
        parent = BY_KEY[n.parent].label if n.parent else ""
        hay = f"{n.label} {parent} {n.keywords} {n.description}".lower()
        if all(word in hay for word in q.split()):
            hits.append(n)
    return hits
