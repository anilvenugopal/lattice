"""Home page count tiles. Features register tiles; the home page never imports feature tables.

A tile counts rows of a registered grid through GridSpec.query, so counts respect the same
roles and row scoping as the grid, and its link opens that grid with the same view and filters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from lattice.components.grid import GridSpec, engine
from lattice.kernel.nav import NODES


@dataclass(frozen=True)
class HomeTile:
    label: str
    spec: GridSpec
    view: str = ""
    filters: dict[str, list[str]] = field(default_factory=dict)
    tone: str = ""            # stat tone, shown only when the count is above zero


TILES: list[HomeTile] = []


def register_tile(tile: HomeTile) -> HomeTile:
    TILES.append(tile)
    return tile


def tiles_for(db: Session, user) -> list[dict]:
    """Tiles the user may see, in navigation order (the order of their grid's page in NODES)."""
    rank = {node.route: i for i, node in reversed(list(enumerate(NODES)))}
    out = []
    for tile in sorted(TILES, key=lambda t: rank.get(t.spec.path, len(rank))):
        if not user.has_any(tile.spec.roles):
            continue
        count = engine.count(tile.spec, db, user,
                             engine.GridQuery(view=tile.view, filters=tile.filters))
        params = [("view", tile.view)] if tile.view else []
        params += [(f"f_{k}", v) for k, values in tile.filters.items() for v in values]
        out.append({"label": tile.label, "value": count, "tone": tile.tone if count else "",
                    "href": tile.spec.path + ("?" + urlencode(params) if params else "")})
    return out
