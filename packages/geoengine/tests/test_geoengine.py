"""geoengine: layers, loading, point-in-area, distances, H3 and quality tiers."""

import pytest
from sqlalchemy import text

import geoengine

SQUARE = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "id": "sq", "properties": {"name": "Square"},
     "geometry": {"type": "Polygon",
                  "coordinates": [[[-95.5, 29.5], [-95.0, 29.5], [-95.0, 30.0],
                                   [-95.5, 30.0], [-95.5, 29.5]]]}}]}
POINTS = [{"id": "in", "lon": -95.2, "lat": 29.7, "quality": "rooftop", "props": {"tiv": 100}},
          {"id": "near", "lon": -94.99, "lat": 29.7, "quality": "zip"},
          {"id": "far", "lon": -90.0, "lat": 29.7}]


def setup(conn):
    areas = geoengine.create_layer(conn, "square", "areas")
    points = geoengine.create_layer(conn, "homes", "points", name="Homes")
    geoengine.put_geojson(conn, areas, SQUARE)
    geoengine.put_points(conn, points, POINTS)
    return areas, points


def test_points_in_an_area(conn):
    setup(conn)
    rows = conn.execute(text("SELECT * FROM geo.points_in('square', 'homes')")).all()
    assert [tuple(r) for r in rows] == [("in", "sq")]


def test_points_within_a_distance(conn):
    setup(conn)
    rows = conn.execute(text(
        "SELECT point_id, round(CAST(distance_m AS numeric)) AS d "
        "FROM geo.within_distance('homes', 'square', 2000) ORDER BY point_id")).all()
    assert [r.point_id for r in rows] == ["in", "near"]        # inside counts as 0 m
    assert rows[0].d == 0 and 900 < rows[1].d < 1100


def test_points_carry_h3_cells_and_quality(conn):
    setup(conn)
    row = conn.execute(text("SELECT h3_5, h3_7, h3_9, quality FROM geo.feature "
                            "WHERE external_id = 'in'")).one()
    assert row.h3_7 == geoengine.cells(29.7, -95.2)["h3_7"] and row.quality == "rooftop"
    assert len(geoengine.boundary(row.h3_7)) == 7               # six corners, closed


def test_putting_a_point_again_moves_it(conn):
    _, points = setup(conn)
    geoengine.put_points(conn, points, [{"id": "far", "lon": -95.1, "lat": 29.6}])
    assert geoengine.count(conn, "homes") == 3
    found = conn.execute(text("SELECT point_id FROM geo.points_in('square', 'homes') "
                              "ORDER BY point_id")).scalars().all()
    assert found == ["far", "in"]


def test_layers_keep_their_kind_and_round_trip_as_geojson(conn):
    setup(conn)
    with pytest.raises(ValueError, match="holds areas"):
        geoengine.create_layer(conn, "square", "points")
    back = geoengine.as_geojson(conn, "square")
    assert back["features"][0]["id"] == "sq" and back["features"][0]["properties"]["name"] == "Square"
    geoengine.delete_layer(conn, "square")
    assert geoengine.count(conn, "square") == 0


def test_unknown_quality_tiers_are_refused(conn):
    _, points = setup(conn)
    with pytest.raises(ValueError, match="unknown quality tier"):
        geoengine.put_points(conn, points, [{"id": "x", "lon": 0, "lat": 0, "quality": "gps"}])


def test_migrations_run_once(conn):
    assert geoengine.migrate(conn) == []
    assert geoengine.schema_version(conn) == "0002_point_view"


def test_quality_tiers():
    assert geoengine.tier_for("ROOFTOP") == "rooftop"
    assert geoengine.tier_for("range_interpolated") == "street"
    assert geoengine.tier_for("something new") == "county"
    assert [t.code for t in geoengine.TIERS] == ["rooftop", "parcel", "street", "zip", "county"]


def test_topojson_to_geojson():
    topology = {"type": "Topology", "transform": {"scale": [1, 1], "translate": [0, 0]},
                "arcs": [[[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]]],
                "objects": {"shapes": {"type": "GeometryCollection", "geometries": [
                    {"type": "Polygon", "id": "01", "arcs": [[0]], "properties": {"n": "A"}}]}}}
    geo = geoengine.to_geojson(topology, "shapes")
    assert geo["features"][0]["id"] == "01"
    assert geo["features"][0]["geometry"]["coordinates"] == [[[0, 0], [1, 0], [1, 1], [0, 1],
                                                              [0, 0]]]


def test_topojson_drops_rings_quantization_collapsed():
    topology = {"type": "Topology",
                "arcs": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], [[5, 5], [5, 5]]],
                "objects": {"shapes": {"type": "GeometryCollection", "geometries": [
                    {"type": "MultiPolygon", "id": "a", "arcs": [[[1]], [[0]]]},
                    {"type": "Polygon", "id": "b", "arcs": [[1]]}]}}}
    geo = geoengine.to_geojson(topology, "shapes")
    assert [f["id"] for f in geo["features"]] == ["a"]
    assert len(geo["features"][0]["geometry"]["coordinates"]) == 1


def test_the_point_view_can_be_filtered_beside_area_layers(conn):
    setup(conn)
    rows = conn.execute(text("SELECT external_id, round(CAST(lon AS numeric), 1) AS lon "
                             "FROM geo.point WHERE layer = 'homes' AND lon IS NOT NULL "
                             "ORDER BY external_id")).all()
    assert [(r.external_id, float(r.lon)) for r in rows] == [("far", -90.0), ("in", -95.2),
                                                              ("near", -95.0)]
