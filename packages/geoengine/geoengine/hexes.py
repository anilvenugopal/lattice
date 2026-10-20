"""H3 hexagons: the cells a point falls in, at the resolutions geoengine stores.

H3 (Uber's hexagonal grid) divides the earth into hexagons at 16 sizes. geoengine stores
three for every point, so totals can be grouped by region, town or block with a plain
GROUP BY. Boundaries are drawn in the browser (h3-js) from the cell id.
"""

from __future__ import annotations

import h3

RESOLUTIONS = {5: "about 250 km², a region", 7: "about 5 km², a town",
               9: "about 0.1 km², a few blocks"}


def cells(lat: float, lon: float) -> dict[str, str]:
    """{"h3_5": …, "h3_7": …, "h3_9": …} for one point."""
    return {f"h3_{r}": h3.latlng_to_cell(lat, lon, r) for r in RESOLUTIONS}


def boundary(cell: str) -> list[tuple[float, float]]:
    """The hexagon's corners as (lon, lat), closed (first corner repeated), for GeoJSON."""
    ring = [(lon, lat) for lat, lon in h3.cell_to_boundary(cell)]
    return ring + ring[:1]
