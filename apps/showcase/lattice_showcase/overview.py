"""The showcase's start page: the story, what each page shows, and what is simulated."""

from __future__ import annotations

from fastapi import APIRouter, Request

from lattice.api import render_page

PAGES = [
    ("Events", "/showcase/events",
     "The catastrophes the carrier is responding to: two closed, one in recovery, Hurricane "
     "Delta live. Each event's page has its lifecycle, totals, map, claims and footprints.",
     "GridSpec, RecordPage, Step, MapSpec"),
    ("Declare event", "/showcase/events/new",
     "A form that changes with the peril. The footprint comes from counties, an uploaded "
     "GeoJSON file or a saved area.", "FormSpec with variants, file upload"),
    ("Exposure", "/showcase/events/4/exposure",
     "The insured locations inside Delta's footprint: by county, hexagon and quality tier. "
     "Draw a shape to narrow the list. Re-run after a new advisory.",
     "MapSpec, spatial grid filter, background job"),
    ("Loss estimate", "/showcase/events/4/loss",
     "A Monte Carlo simulation of what Delta could cost: 1,000 storms, the 1-in-100 loss and "
     "the exceedance curve. Illustrative, with every assumption stated.",
     "Background job, histogram, exceedance"),
    ("Claims", "/showcase/claims",
     "Claims from the claims system across events: bulk assignment, priority, the map, "
     "claims per day since landfall.", "GridSpec, bulk actions, ChartSpec"),
    ("Claim page", "/showcase/claims/1",
     "Status, the damage assessment, field reports, coverages as a tree, where it is, "
     "comments and history.", "RecordPage, TreeNode, panels"),
    ("Live intake", "/showcase/intake",
     "New claims arriving for Delta, from a simulator you can start, pause and speed up.",
     "GridSpec(poll_seconds=…)"),
    ("Deployment", "/showcase/deployment",
     "Zones, leads and surveyors as a graph; act on a zone from its node.",
     "Graph with node actions"),
    ("Field reports", "/showcase/field-reports",
     "Free-form reports from surveyors, read beside the list. No two have the same fields.",
     "GridSpec(layout=\"split\"), FormSpec(schema=None)"),
    ("Notices", "/showcase/notices",
     "What you are told about the claims you handle. Only you see yours.",
     "Row-level access in the grid query"),
    ("Locations", "/showcase/locations",
     "The 42,000 insured locations. Draw a polygon, rectangle or circle and the list, "
     "totals and charts follow; save the shape as an area.",
     "Spatial grid filter, map drawing"),
]

# What the showcase does itself, and what it stands in for.
SOURCES = [
    ("Insured locations", "Policy administration and the exposure warehouse, as a nightly "
     "snapshot", "42,659 synthetic locations in real metro areas, seeded"),
    ("Claims", "The claims system; new claims pulled every few minutes",
     "Seeded for past events; a labelled simulator for Delta"),
    ("Hurricane forecast", "National Hurricane Center advisories", "Three sample advisory cones"),
    ("Loss estimate", "A licensed catastrophe model", "A simple, stated Monte Carlo"),
    ("Events, footprints, exposure runs, assignments, assessments, field reports, notices, "
     "comments", "This app", "This app"),
]

router = APIRouter()


@router.get("")
def overview(request: Request):
    return render_page(request, "showcase/overview.html", "overview", pages=PAGES,
                       sources=SOURCES)
