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
    key: str
    label: str
    route: str
    parent: str | None = None
    icon: str | None = None          # rail icon name, see lattice/kernel/icons.py
    roles: tuple[str, ...] = ()      # empty = every signed-in user
    hidden: bool = False             # routing/breadcrumb only
    bottom: bool = False             # rail bottom group
    keywords: str = ""               # extra Ctrl+J match terms
    description: str = ""
    app: str = ""                    # owning app key, set when registered


# Filled by lattice.host.create_app from the app manifests, in rail order.
NODES: list[NavNode] = []
BY_KEY: dict[str, NavNode] = {}


def reset() -> None:
    NODES.clear()
    BY_KEY.clear()


def add(nodes: list[NavNode], app_key: str) -> None:
    """Register an app's nodes, tagged with the app that owns them."""
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


def nav_context(user, active_key: str) -> dict:
    """Everything base/shell.html needs to draw rail, sidebar and breadcrumb."""
    chain = _chain(active_key)
    section = chain[0]
    visible = [n for n in NODES if user.has_any(n.roles)]
    sidebar = [n for n in visible if n.parent == section.key and not n.hidden]
    # The highlighted sidebar entry is the nearest visible ancestor of the active node.
    sidebar_keys = {n.key for n in sidebar}
    active_item = next((n.key for n in reversed(chain) if n.key in sidebar_keys), None)
    return {
        "rail": [n for n in visible if n.parent is None and not n.bottom],
        "rail_bottom": [n for n in visible if n.parent is None and n.bottom],
        "section": section,
        "sidebar": sidebar,
        "active_key": active_key,
        "active_item": active_item,
        "breadcrumb": chain,
        "title": chain[-1].label,
    }


def search_nodes(user, q: str) -> list[NavNode]:
    q = q.lower().strip()
    hits = []
    for n in NODES:
        if n.hidden or not user.has_any(n.roles):
            continue
        parent = BY_KEY[n.parent].label if n.parent else ""
        hay = f"{n.label} {parent} {n.keywords} {n.description}".lower()
        if all(word in hay for word in q.split()):
            hits.append(n)
    return hits
