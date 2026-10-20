"""geoengine: spatial data and computation on Postgres and PostGIS.

Layers of points and areas in schema `geo`; point-in-area matching and distances as SQL
functions (`geo.points_in`, `geo.within_distance`) that callers use in their own queries;
H3 hexagons and location quality tiers on every point. It knows nothing of Lattice or of
insurance. The public contract is docs/public_contract.md.
"""

from geoengine.hexes import RESOLUTIONS, boundary, cells
from geoengine.layers import (
    as_geojson,
    clear_layer,
    count,
    create_layer,
    delete_layer,
    put_geojson,
    put_points,
)
from geoengine.migrate import SCHEMA, migrate, schema_version
from geoengine.quality import TIERS, Tier, tier_for
from geoengine.topojson import to_geojson

__version__ = "0.1.0"

__all__ = ["RESOLUTIONS", "SCHEMA", "TIERS", "Tier", "__version__", "as_geojson", "boundary",
           "cells", "clear_layer", "count", "create_layer", "delete_layer", "migrate",
           "put_geojson", "put_points", "schema_version", "tier_for", "to_geojson"]
