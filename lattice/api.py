"""The public API of Lattice: the only module an app may import (ADR 0002).

Everything else under `lattice` is internal and may change without notice.
Removing or changing a name here is a breaking change.
"""

from lattice.components.grid import (
    Action,
    ActionContext,
    ActionResult,
    Column,
    Field,
    Filter,
    GridSpec,
    Palette,
    View,
    build_grid,
    render_grid_page,
)
from lattice.components.manifest import AppManifest
from lattice.components.search.providers import SearchProvider, SearchResult
from lattice.components.tiles import HomeTile
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user, require_roles
from lattice.kernel.auth.roles import ADMINS, EDITORS
from lattice.kernel.config import settings
from lattice.kernel.database import Db, NotFound, get_db, transaction
from lattice.kernel.dev_seed import DEV_USERS
from lattice.kernel.nav import NavNode
from lattice.kernel.services import audit, users
from lattice.kernel.sql import Query, sql_queries
from lattice.kernel.web import flash, render, render_page, toast

__all__ = [
    # Apps and navigation
    "AppManifest", "NavNode", "HomeTile", "SearchProvider", "SearchResult",
    # Grid
    "Action", "ActionContext", "ActionResult", "Column", "Field", "Filter", "GridSpec",
    "Palette", "View", "build_grid", "render_grid_page",
    # Pages and feedback
    "render", "render_page", "flash", "toast",
    # Requests and access
    "csrf_protect", "current_user", "require_roles", "ADMINS", "EDITORS",
    # Data
    "Db", "get_db", "transaction", "NotFound", "Query", "sql_queries",
    "audit", "users", "settings",
    # Development data
    "DEV_USERS",
]
