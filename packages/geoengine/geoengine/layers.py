"""Layers of points and areas, and loading them. Every function takes a SQLAlchemy
Connection and works inside the caller's transaction."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Literal

from sqlalchemy import Connection

from geoengine import hexes, quality
from geoengine._sql import load

Q = load("layers")


def create_layer(conn: Connection, key: str, kind: Literal["points", "areas"],
                 name: str = "") -> int:
    """Create the layer (or rename an existing one with this key); returns its id."""
    row = conn.execute(Q["create_layer"], {"key": key, "name": name or key, "kind": kind}).one()
    if row.kind != kind:
        raise ValueError(f"Layer {key!r} holds {row.kind}, not {kind}")
    return row.id


def delete_layer(conn: Connection, key: str) -> None:
    conn.execute(Q["delete_layer"], {"key": key})


def clear_layer(conn: Connection, layer_id: int) -> None:
    conn.execute(Q["clear_layer"], {"layer_id": layer_id})


def put_points(conn: Connection, layer_id: int, points: Iterable[dict]) -> int:
    """Add or move points. Each is {"id", "lon", "lat"}, optionally "quality" (a tier code)
    and "props" (a dict). H3 cells are computed. Returns how many."""
    rows = []
    for p in points:
        tier = p.get("quality")
        if tier is not None and tier not in quality.BY_CODE:
            raise ValueError(f"Point {p['id']!r}: unknown quality tier {tier!r}")
        rows.append({"layer_id": layer_id, "external_id": str(p["id"]), "lon": p["lon"],
                     "lat": p["lat"], "quality": tier, "props": json.dumps(p.get("props", {})),
                     **hexes.cells(p["lat"], p["lon"])})
    if rows:
        conn.execute(Q["put_point"], rows)
    return len(rows)


def put_geojson(conn: Connection, layer_id: int, collection: dict,
                id_property: str = "") -> int:
    """Add or replace the features of a GeoJSON FeatureCollection as areas. Each feature's id
    is its `id`, or the property `id_property`. Returns how many."""
    rows = []
    for i, f in enumerate(collection.get("features", [])):
        props = f.get("properties") or {}
        external_id = props.get(id_property) if id_property else f.get("id")
        rows.append({"layer_id": layer_id, "external_id": str(external_id if external_id is not None else i),
                     "geometry": json.dumps(f["geometry"]), "props": json.dumps(props)})
    if rows:
        conn.execute(Q["put_area"], rows)
    return len(rows)


def as_geojson(conn: Connection, key: str) -> dict:
    """A layer as a GeoJSON FeatureCollection, for a map."""
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": r.external_id, "properties": r.props,
         "geometry": json.loads(r.geometry)}
        for r in conn.execute(Q["as_geojson"], {"key": key})]}


def count(conn: Connection, key: str) -> int:
    return conn.execute(Q["count"], {"key": key}).scalar_one()
