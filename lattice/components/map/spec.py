"""Declarative maps (ADR 0013). One MapSpec per map, on a grid's rows, like a ChartSpec.

Layers are drawn bottom to top over a basemap:

    MapSpec("showcase.exposure", "Exposed locations", source=EXPOSURE_GRID, layers=[
        Regions("county_fips", value=Sum("tiv", "Insured value"), map="us-counties"),
        Hexagons("h3_7", value=Sum("tiv", "Insured value")),
        Points("lon", "lat", color="quality", label="{ref}"),
        Areas("footprint", "Footprint", load=footprint_geojson),
    ])

Points, hexagons and regions come from the grid's query, narrowed by its view, filters
and search, and grouped in the database; the grid's query is the access boundary. Areas
come from a function, such as a geoengine layer as GeoJSON.

Guide: lattice/help/developer/building-apps/maps.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from lattice.components.chart.spec import Count, Measure
from lattice.components.grid.spec import GridSpec, Tone


@dataclass(frozen=True)
class Points:
    """One dot per row, at the row's longitude and latitude."""

    lon: str                        # column with longitude (WGS 84)
    lat: str                        # column with latitude
    color: str = ""                 # a column whose value colours the dot: its Column's tones,
                                    # else a fixed palette
    label: str = "{id}"             # popup text, formatted with the row
    title: str = "Locations"        # legend text
    limit: int = 20_000             # at most this many dots; the rest are left out, and said so


@dataclass(frozen=True)
class Hexagons:
    """A measure per H3 cell, shaded from light to dark."""

    cell: str                       # column holding an H3 cell id (e.g. geoengine's h3_7)
    value: Measure = field(default_factory=Count)
    title: str = ""


@dataclass(frozen=True)
class Regions:
    """A measure per US state or county, shaded from light to dark."""

    key: str                        # column with the FIPS code: 2 digits (state) or 5 (county)
    value: Measure = field(default_factory=Count)
    map: Literal["us-states", "us-counties"] = "us-states"
    title: str = ""


@dataclass(frozen=True)
class Areas:
    """Shapes from a function, not the grid: a fire perimeter, a forecast cone."""

    key: str                        # unique in the map
    title: str
    load: Callable[[Any, Any], dict]  # (db, user) -> GeoJSON FeatureCollection
    tone: Tone = "danger"           # outline and fill colour


Layer = Points | Hexagons | Regions | Areas


@dataclass
class MapSpec:
    key: str                        # unique: "{app}.{name}"
    title: str
    source: GridSpec                # rows for points, hexagons and regions
    layers: list[Layer] = field(default_factory=list)   # bottom to top
    height: int = 440               # pixels
    format: Literal["number", "money", "percent"] = "number"   # values in legends and popups
    permission: str = ""            # on top of the grid's own

    @property
    def app_key(self) -> str:
        return self.key.partition(".")[0] if "." in self.key else ""

    def columns(self) -> list[str]:
        """Query columns the map reads; each must be in the grid's query."""
        cols: list[str] = []
        for layer in self.layers:
            if isinstance(layer, Points):
                cols += [layer.lon, layer.lat, layer.color]
            elif isinstance(layer, Hexagons):
                cols += [layer.cell, getattr(layer.value, "column", "")]
            elif isinstance(layer, Regions):
                cols += [layer.key, getattr(layer.value, "column", "")]
        return [c for c in cols if c]

    def check(self) -> None:
        keys = [layer.key for layer in self.layers if isinstance(layer, Areas)]
        if len(keys) != len(set(keys)):
            raise ValueError(f"map {self.key!r}: two Areas layers share a key")
        if not self.layers:
            raise ValueError(f"map {self.key!r} has no layers")
