"""The public API of Lattice: the only module an app may import (ADR 0002).

Everything else under `lattice` is internal and may change without notice.
Removing or changing a name here is a breaking change.
"""

from lattice.components import documents
from lattice.components.chart import (
    Avg,
    ChartSpec,
    Count,
    Max,
    Min,
    Sum,
    Threshold,
    Time,
    build_chart,
)
from lattice.components.documents import DocumentKind, InvalidDocument
from lattice.components.flows import Graph, GraphEdge, GraphNode, Step, TreeNode, build_graph
from lattice.components.forms import FormResult, FormSpec, SchemaDef, build_form, parse_form
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
from lattice.components.map import Areas, Hexagons, MapSpec, Points, Regions, build_map
from lattice.components.record import Link, Panel, RecordPage, RecordPanel, render_record_page
from lattice.components.references import Ref, ReferenceKind, Resolved, parse, urn
from lattice.components.references import resolve as resolve_ref
from lattice.components.search.providers import SearchProvider, SearchResult
from lattice.components.tiles import HomeTile
from lattice.components.timeline import TimelineSpec, build_timeline
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user, require
from lattice.kernel.auth.permissions import Permission
from lattice.kernel.config import settings
from lattice.kernel.database import Db, NotFound, get_db, transaction
from lattice.kernel.dev_seed import DEV_USERS
from lattice.kernel.events import CloudEvent
from lattice.kernel.migrate import Library
from lattice.kernel.nav import NavNode
from lattice.kernel.services import audit, users
from lattice.kernel.sql import Query, sql_queries
from lattice.kernel.web import flash, render, render_page, toast

__all__ = [
    # Apps and navigation
    "AppManifest", "Library", "NavNode", "HomeTile", "SearchProvider", "SearchResult",
    # Grid
    "Action", "ActionContext", "ActionResult", "Column", "Field", "Filter", "GridSpec",
    "Palette", "View", "build_grid", "render_grid_page",
    # Record pages
    "RecordPage", "Panel", "Link", "render_record_page",
    # Working across apps (ADR 0011)
    "Ref", "ReferenceKind", "Resolved", "urn", "parse", "resolve_ref", "RecordPanel",
    "CloudEvent",
    # Maps
    "MapSpec", "Points", "Hexagons", "Regions", "Areas", "build_map",
    # Timelines
    "TimelineSpec", "build_timeline",
    # Charts
    "ChartSpec", "Count", "Sum", "Avg", "Min", "Max", "Time", "Threshold", "build_chart",
    # Forms from JSON Schema
    "FormSpec", "SchemaDef", "FormResult", "build_form", "parse_form",
    "DocumentKind", "InvalidDocument", "documents",
    # Flows
    "Step", "TreeNode", "Graph", "GraphNode", "GraphEdge", "build_graph",
    # Pages and feedback
    "render", "render_page", "flash", "toast",
    # Requests and access
    "csrf_protect", "current_user", "require", "Permission",
    # Data
    "Db", "get_db", "transaction", "NotFound", "Query", "sql_queries",
    "audit", "users", "settings",
    # Development data
    "DEV_USERS",
]
