"""Timelines: bars on a time axis, in lanes, from a grid's rows (ADR 0014).

    TimelineSpec("showcase.workload", "Surveyor workload", source=CLAIMS_GRID,
                 start="assigned_at", end="inspected_at", lane="surveyor",
                 label="{claim_number} · {insured}", tone="severity",
                 href="/showcase/claims/{id}")

One row is one bar (a segment): several rows with the same lane are several bars in it.
A row with no end is still going and is drawn to now. A row whose `marker` column is set
is drawn as a marker at its start. The rows come from the grid's query, narrowed by its
view, filters and search, and by the window shown; the grid's query is the access boundary.

Guide: lattice/help/developer/building-apps/timelines.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from lattice.components.grid.spec import GridSpec


@dataclass
class TimelineSpec:
    key: str                        # unique: "{app}.{name}"
    title: str
    source: GridSpec                # the rows; its query is the access boundary
    start: str                      # timestamp column: where the bar starts
    lane: str                       # column grouping bars into lanes; its Column labels name them
    end: str = ""                   # timestamp column: where it ends; NULL means still going.
                                    # Without one, every row is a marker
    label: str = "{id}"             # bar text and tooltip, formatted with the row
    tone: str = ""                  # column whose Column.tones colour the bar
    marker: str = ""                # column: when true, the row is a marker at `start`
    href: str = ""                  # click opens this, formatted with the row ("/x/{id}");
                                    # else a linked grid on the page opens the row's panel
    lane_order: str = "start"       # "start": lanes in order of their first bar; "lane": by value
    limit: int = 2000               # bars per window; past it, the timeline asks to zoom in
    height: int = 0                 # pixels; 0 sizes to the lanes
    poll_seconds: int = 0           # redraw every n seconds, so open bars grow
    permission: str = ""            # on top of the grid's own

    @property
    def app_key(self) -> str:
        return self.key.partition(".")[0] if "." in self.key else ""

    def columns(self) -> list[str]:
        """Query columns the timeline reads; each must be in the grid's query."""
        return [c for c in (self.start, self.end, self.lane, self.tone, self.marker) if c]

    def check(self) -> None:
        if self.lane_order not in ("start", "lane"):
            raise ValueError(f"timeline {self.key!r}: lane_order must be 'start' or 'lane'")
        if self.limit < 1:
            raise ValueError(f"timeline {self.key!r}: limit must be at least 1")
