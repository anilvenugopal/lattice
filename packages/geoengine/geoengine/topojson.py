"""TopoJSON to GeoJSON. Map boundary files (US states and counties) are usually published as
TopoJSON, which shares borders between neighbours to stay small; PostGIS reads GeoJSON.
"""

from __future__ import annotations


def to_geojson(topology: dict, object_name: str) -> dict:
    """The named object of a TopoJSON topology as a GeoJSON FeatureCollection."""
    transform = topology.get("transform")
    arcs = [_decode(arc, transform) for arc in topology["arcs"]]

    def arc(i: int) -> list:
        return arcs[i] if i >= 0 else arcs[~i][::-1]

    def ring(indexes: list[int]) -> list:
        points: list = []
        for i in indexes:
            part = arc(i)
            points.extend(part if not points else part[1:])
        return points

    def geometry(g: dict) -> dict | None:
        kind = g["type"]
        if kind == "Polygon":
            return {"type": kind, "coordinates": [ring(r) for r in g["arcs"]]}
        if kind == "MultiPolygon":
            return {"type": kind, "coordinates": [[ring(r) for r in p] for p in g["arcs"]]}
        if kind == "LineString":
            return {"type": kind, "coordinates": ring(g["arcs"])}
        if kind == "Point":
            return {"type": kind, "coordinates": _point(g["coordinates"], transform)}
        return None

    features = []
    for g in topology["objects"][object_name]["geometries"]:
        geom = geometry(g)
        if geom is not None:
            features.append({"type": "Feature", "id": g.get("id"),
                             "properties": g.get("properties", {}), "geometry": geom})
    return {"type": "FeatureCollection", "features": features}


def _point(p, transform):
    if not transform:
        return list(p)
    (sx, sy), (tx, ty) = transform["scale"], transform["translate"]
    return [p[0] * sx + tx, p[1] * sy + ty]


def _decode(arc: list, transform) -> list:
    """Arcs in a quantized topology are delta-encoded: each point is an offset from the last."""
    if not transform:
        return [list(p) for p in arc]
    x = y = 0
    out = []
    for dx, dy in arc:
        x, y = x + dx, y + dy
        out.append(_point((x, y), transform))
    return out
