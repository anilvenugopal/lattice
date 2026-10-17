"""Navigation manifest: the only place navigation structure is declared.

Rail, sidebar, breadcrumbs, page titles, role gating of menus and the Ctrl+J
palette all derive from NODES. Adding a page = one NavNode + one route.

A route passes its node key to `render_page(..., nav_key=...)`.
Top-level nodes (parent=None) are rail icons. Their children are the sidebar.
`hidden=True` nodes (detail pages) never show in menus but still resolve
breadcrumbs and keep their parent highlighted.
"""

from __future__ import annotations

from dataclasses import dataclass

from lattice.kernel.auth.roles import ADMINS


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


NODES: list[NavNode] = [
    # ── Rail ────────────────────────────────────────────────────────────────
    NavNode("home", "Home", "/", icon="home", description="Overview and recent activity"),
    NavNode("work", "Work Queue", "/work", icon="queue",
            keywords="submissions cases requests tickets",
            description="Table grid with views, bulk actions, side panel and detail pages"),
    NavNode("jobs", "Jobs", "/jobs", icon="activity", keywords="tasks runs background",
            description="Live-polling grid with state-dependent actions"),
    NavNode("inbox", "Inbox", "/inbox", icon="inbox", keywords="mail email messages",
            description="Split layout: message list and reading pane"),
    NavNode("admin", "Administration", "/admin/users", icon="shield", roles=ADMINS,
            description="Users, roles, sessions, audit log and system settings"),
    NavNode("account", "Account", "/account/preferences", icon="user", bottom=True),

    # ── Work Queue ──────────────────────────────────────────────────────────
    NavNode("work.items", "Items", "/work", parent="work"),
    NavNode("work.new", "New item", "/work/new", parent="work", keywords="create add"),
    NavNode("work.detail", "Detail", "/work", parent="work.items", hidden=True),

    # Jobs has no children, so its pages render without a sidebar.

    # ── Inbox ───────────────────────────────────────────────────────────────
    NavNode("inbox.inbox", "Inbox", "/inbox", parent="inbox"),
    NavNode("inbox.starred", "Starred", "/inbox?view=starred", parent="inbox"),
    NavNode("inbox.archive", "Archive", "/inbox?view=archive", parent="inbox"),

    # ── Administration ──────────────────────────────────────────────────────
    NavNode("admin.users", "Users", "/admin/users", parent="admin", roles=ADMINS,
            keywords="accounts people"),
    NavNode("admin.user", "User", "/admin/users", parent="admin.users", roles=ADMINS,
            hidden=True),
    NavNode("admin.roles", "Roles", "/admin/roles", parent="admin", roles=ADMINS,
            keywords="permissions"),
    NavNode("admin.sessions", "Sessions", "/admin/sessions", parent="admin", roles=ADMINS),
    NavNode("admin.audit", "Audit log", "/admin/audit", parent="admin", roles=ADMINS,
            keywords="history events"),
    NavNode("admin.system", "System", "/admin/system", parent="admin", roles=ADMINS,
            keywords="configuration settings health"),
    NavNode("admin.uikit", "UI kit", "/admin/ui-kit", parent="admin", roles=ADMINS,
            keywords="components styles gallery"),

    # ── Account ─────────────────────────────────────────────────────────────
    NavNode("account.preferences", "Preferences", "/account/preferences", parent="account",
            keywords="theme dark light density settings"),
    NavNode("account.profile", "Profile", "/account/profile", parent="account"),
    NavNode("account.security", "Security", "/account/security", parent="account",
            keywords="password sessions sign out"),
]

BY_KEY: dict[str, NavNode] = {n.key: n for n in NODES}


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
