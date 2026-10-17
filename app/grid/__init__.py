"""Standard data grid. See docs/GRID.md."""

from app.grid.render import build_grid, render_grid_page
from app.grid.router import REGISTRY, register
from app.grid.spec import (
    Action,
    ActionContext,
    ActionResult,
    Column,
    Field,
    Filter,
    GridSpec,
    Palette,
    View,
)

__all__ = [
    "REGISTRY", "Action", "ActionContext", "ActionResult", "Column", "Field", "Filter",
    "GridSpec", "Palette", "View", "build_grid", "register", "render_grid_page",
]
