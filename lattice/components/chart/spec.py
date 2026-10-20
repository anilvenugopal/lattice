"""Declarative chart definition (ADR 0004). One ChartSpec per chart.

A chart draws a grid's rows, aggregated in the database: the grid's query,
narrowed by its view, filters, search and fixed filters, then grouped by `x`
(and `series`) with one measure. The grid's query is the access boundary, as
for every other read.

Guide: lattice/help/developer/building-apps/charts.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from lattice.components.grid.spec import GridSpec, Tone

ChartKind = Literal["bar", "line", "area", "pie", "doughnut", "calendar", "treemap", "sankey",
                    "choropleth", "histogram", "exceedance"]
TimeUnit = Literal["hour", "day", "week", "month", "quarter", "year"]
ValueFormat = Literal["number", "money", "percent"]


@dataclass(frozen=True)
class Time:
    """A time dimension: the column truncated to `unit` (Postgres date_trunc)."""

    column: str
    unit: TimeUnit = "day"


@dataclass(frozen=True)
class Count:
    """Rows per group."""

    label: str = "Count"


@dataclass(frozen=True)
class Sum:
    column: str
    label: str = ""


@dataclass(frozen=True)
class Avg:
    column: str
    label: str = ""


@dataclass(frozen=True)
class Min:
    column: str
    label: str = ""


@dataclass(frozen=True)
class Max:
    column: str
    label: str = ""


Measure = Count | Sum | Avg | Min | Max


@dataclass(frozen=True)
class Threshold:
    """A horizontal line across a bar, line or area chart, e.g. a target or a limit."""

    value: float
    label: str = ""
    tone: Tone = "danger"


@dataclass
class ChartSpec:
    """One chart over a grid's rows.

    kind and its dimensions:
      bar, line, area   x (a column or Time), optional series (one dataset per value)
      pie, doughnut     x (a column)
      calendar          x = Time(column, "day"): one month as a calendar, shaded by the measure;
                        it opens on the busiest day's month, with buttons for the others
      histogram         x (a numeric column): how many rows fall in each of `bins` ranges
      exceedance        x (a numeric column): the chance a value exceeds each amount, e.g.
                        losses across simulations; thresholds mark probabilities in %
      treemap           x (a column), optional series (groups)
      sankey            x (from) and series (to): flows between two columns
      choropleth        x: a column of country names or ISO 3166 numeric codes
    """

    key: str                        # unique: "{app}.{name}"
    title: str                      # heading above the chart
    source: GridSpec                # the rows: its query, filters and access boundary
    kind: ChartKind = "bar"
    x: str | Time = ""              # the category or time axis
    y: Measure = field(default_factory=Count)  # what is measured per group
    series: str = ""                # a column splitting the data into datasets
    stacked: bool = False           # bar and area: stack the series
    horizontal: bool = False        # bar: bars run left to right
    limit: int = 12                 # category charts: the largest n categories; the rest is "Other"
    bins: int = 20                  # histogram: how many equal ranges
    thresholds: list[Threshold] = field(default_factory=list)  # bar, line, area
    format: ValueFormat = "number"  # how values show in tooltips and the axis
    height: int = 280               # pixels
    permission: str = ""            # who may see it, in addition to the grid's permission
    # Clicking a bar, slice, box or day narrows the list to it: the grid on the same page
    # (linked charts), or this list page, opened with the chart's rows narrowed further.
    drill: str = ""                 # e.g. "/showcase/claims"
    empty_text: str = "No data for these filters."

    @property
    def app_key(self) -> str:
        return self.key.partition(".")[0] if "." in self.key else ""

    @property
    def measure_label(self) -> str:
        return self.y.label or f"{type(self.y).__name__} of {self.y.column}"

    def columns(self) -> list[str]:
        """Query columns the chart reads; each must be in the grid's query."""
        cols = [self.x.column if isinstance(self.x, Time) else self.x, self.series,
                getattr(self.y, "column", "")]
        return [c for c in cols if c]

    def check(self) -> None:
        """Raise ValueError when the kind and its dimensions don't fit together."""
        time = isinstance(self.x, Time)
        if not self.x:
            raise ValueError(f"chart {self.key!r} needs x")
        if self.kind == "calendar" and not (time and self.x.unit == "day"):
            raise ValueError(f"chart {self.key!r}: a calendar needs x=Time(column, 'day')")
        if self.kind in ("pie", "doughnut", "treemap", "sankey", "choropleth") and time:
            raise ValueError(f"chart {self.key!r}: a {self.kind} needs a column for x, not Time")
        if self.kind == "sankey" and not self.series:
            raise ValueError(f"chart {self.key!r}: a sankey needs series (the 'to' column)")
        if self.kind in ("histogram", "exceedance") and (time or self.series):
            raise ValueError(f"chart {self.key!r}: a {self.kind} needs a numeric column for x "
                             "and no series")
        if self.kind in ("pie", "doughnut", "choropleth", "calendar") and self.series:
            raise ValueError(f"chart {self.key!r}: a {self.kind} has no series")
