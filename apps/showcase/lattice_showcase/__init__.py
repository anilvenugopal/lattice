"""The showcase: a carrier responding to catastrophes, built with every Lattice component.

Events and their footprints, exposure, a Monte Carlo loss estimate, claims with their
assessments and field reports, live intake, deployment, notices and the location map.
The systems of record (policies, claims, forecasts) are simulated, and say so on screen.
"""

import asyncio
from pathlib import Path

import geoengine
from lattice.api import AppManifest, NavNode
from lattice_showcase import (
    cat_seed,
    claims,
    deployment,
    events,
    exposure,
    links,
    locations,
    losses,
    notices,
    overview,
)

HERE = Path(__file__).parent


async def background() -> None:
    """The showcase's development simulators: exposure runs, claims intake, loss estimates."""
    await asyncio.gather(exposure.background(), claims.background(), losses.background())

APP = AppManifest(
    key="showcase",
    label="Showcase",
    icon="showcase:app",
    help_url="/help/showcase",
    icons={"app": '<rect x="3" y="3" width="7" height="18" rx="1.5"/>'
                  '<rect x="13" y="3" width="8" height="7" rx="1.5"/>'
                  '<rect x="13" y="13" width="8" height="8" rx="1.5"/>',
           "storm": '<path d="M12 4a8 8 0 1 0 8 8"/><path d="M12 8a4 4 0 1 1-4 4"/><circle cx="12" cy="12" r="1"/>',
           "map": '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/>'},
    static=HERE / "static",
    stylesheets=["showcase.css"],
    routers=[overview.router, events.router, exposure.router, locations.router, claims.router,
             deployment.router, losses.router, notices.router],
    grids=[events.GRID, exposure.GRID, exposure.RUNS, locations.GRID, claims.GRID, claims.REPORTS,
           claims.INTAKE, claims.PROGRESS, deployment.ZONES, events.STAGES_GRID, losses.SAMPLES,
           losses.RUNS, notices.GRID],
    timelines=[events.TIMELINE, claims.TIMELINE, deployment.WORKLOAD],
    charts=[*exposure.CHARTS, *locations.CHARTS, *claims.CHARTS, *claims.EVENT_CHARTS,
            claims.INTAKE_CHART, *losses.CHARTS],
    maps=[exposure.MAP, locations.MAP, claims.MAP],
    documents=[claims.ASSESSMENT, claims.REPORT],
    forms=[events.DECLARE, exposure.FOOTPRINT_FORM, claims.REPORT_FORM],
    references=links.REFERENCES,
    subscribes={"comments.added": links.notify_handler},
    permissions=[*events.PERMISSIONS, *claims.PERMISSIONS],
    tiles=[*claims.TILES, *notices.TILES],
    background=background,
    seed=cat_seed.seed,
    templates=HERE / "templates",
    help=HERE / "help",
    sql=HERE / "sql",
    library_schemas=[geoengine.SCHEMA],
    nav=[
        NavNode("overview", "Showcase", "/showcase", icon="showcase:app",
                keywords="demo examples components catastrophe story",
                description="A carrier responding to catastrophes, on every Lattice component"),
        NavNode("events", "Events", "/showcase/events", icon="showcase:storm",
                keywords="catastrophe cat hurricane hail wildfire freeze",
                description="Catastrophes the carrier is responding to"),
        NavNode("events.list", "Events", "/showcase/events", parent="events"),
        NavNode("events.new", "Declare event", "/showcase/events/new", parent="events",
                permission=events.MANAGE, keywords="new catastrophe"),
        NavNode("events.event", "Event", "/showcase/events", parent="events.list", hidden=True),
        NavNode("events.exposure", "Exposure", "/showcase/events", parent="events.event",
                hidden=True),
        NavNode("events.loss", "Loss estimate", "/showcase/events", parent="events.event",
                hidden=True),
        NavNode("claims", "Claims", "/showcase/claims", icon="queue", keywords="fnol losses",
                description="Claims across events, from the claims system"),
        NavNode("claims.list", "Claims", "/showcase/claims", parent="claims"),
        NavNode("claims.claim", "Claim", "/showcase/claims", parent="claims.list", hidden=True),
        NavNode("claims.intake", "Live intake", "/showcase/intake", parent="claims",
                keywords="fnol new claims arriving simulator"),
        NavNode("claims.deployment", "Deployment", "/showcase/deployment", parent="claims",
                keywords="surveyors zones teams graph"),
        NavNode("claims.reports", "Field reports", "/showcase/field-reports", parent="claims",
                keywords="surveyor notes inspection"),
        NavNode("claims.notices", "Notices", "/showcase/notices", parent="claims",
                keywords="notifications comments messages"),
        NavNode("locations", "Locations", "/showcase/locations", icon="showcase:map",
                keywords="exposure portfolio map draw search",
                description="The exposure snapshot, searched on the map"),
    ],
)
