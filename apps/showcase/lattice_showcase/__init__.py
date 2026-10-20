"""The showcase: every Lattice component on sample data, one page per capability.

Grids (Items, Live updates, Reading pane), the record page, the plain form pattern,
charts, forms from JSON Schema with the document store, and flows. The data is sample
data; nothing here models a business.
"""

import asyncio
from pathlib import Path

import geoengine
from lattice.api import AppManifest, NavNode
from lattice_showcase import (
    charts,
    claims,
    deployment,
    events,
    exposure,
    flows,
    inbox,
    items,
    jobs,
    links,
    locations,
    overview,
    specs,
)
from lattice_showcase.seed import seed

HERE = Path(__file__).parent


async def background() -> None:
    """The showcase's development simulators: jobs moving along, exposure runs running."""
    await asyncio.gather(jobs.background(), exposure.background(), claims.background())

APP = AppManifest(
    key="showcase",
    label="Showcase",
    icon="showcase:app",
    help_url="/help/showcase",
    icons={"app": '<rect x="3" y="3" width="7" height="18" rx="1.5"/>'
                  '<rect x="13" y="3" width="8" height="7" rx="1.5"/>'
                  '<rect x="13" y="13" width="8" height="8" rx="1.5"/>',
           "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
           "form": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
           "storm": '<path d="M12 4a8 8 0 1 0 8 8"/><path d="M12 8a4 4 0 1 1-4 4"/><circle cx="12" cy="12" r="1"/>',
           "map": '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/>',
           "flow": '<rect x="3" y="4" width="6" height="5" rx="1"/><rect x="15" y="4" width="6" height="5" rx="1"/>'
                   '<rect x="9" y="15" width="6" height="5" rx="1"/><path d="M6 9v3h12V9M12 12v3"/>'},
    static=HERE / "static",
    stylesheets=["showcase.css"],
    routers=[overview.router, events.router, exposure.router, locations.router, claims.router,
             deployment.router,
             items.router, jobs.router, inbox.router, charts.router, specs.router, flows.router],
    grids=[events.GRID, exposure.GRID, exposure.RUNS, locations.GRID, claims.GRID, claims.REPORTS,
           claims.INTAKE, deployment.ZONES,
           items.GRID, jobs.GRID, inbox.GRID, specs.GRID],
    charts=[*exposure.CHARTS, *locations.CHARTS, *claims.CHARTS, *claims.EVENT_CHARTS,
            claims.INTAKE_CHART, *charts.CHARTS],
    maps=[exposure.MAP, locations.MAP, claims.MAP],
    documents=[specs.SPEC, specs.NOTE, claims.ASSESSMENT, claims.REPORT],
    forms=[specs.FREEFORM, events.DECLARE, exposure.FOOTPRINT_FORM, claims.REPORT_FORM],
    references=links.REFERENCES,
    subscribes={"comments.added": links.notify_owner},
    permissions=[*events.PERMISSIONS, *claims.PERMISSIONS, *items.PERMISSIONS,
                 *specs.PERMISSIONS],
    tiles=[*items.TILES, *jobs.TILES, *inbox.TILES],
    background=background,
    seed=seed,
    templates=HERE / "templates",
    help=HERE / "help",
    sql=HERE / "sql",
    library_schemas=[geoengine.SCHEMA],
    nav=[
        NavNode("overview", "Showcase", "/showcase", icon="showcase:app",
                keywords="demo examples components gallery",
                description="Every Lattice component on sample data"),
        NavNode("events", "Events", "/showcase/events", icon="showcase:storm",
                keywords="catastrophe cat hurricane hail wildfire freeze",
                description="Catastrophes the carrier is responding to"),
        NavNode("events.list", "Events", "/showcase/events", parent="events"),
        NavNode("events.new", "Declare event", "/showcase/events/new", parent="events",
                permission=events.MANAGE, keywords="new catastrophe"),
        NavNode("events.event", "Event", "/showcase/events", parent="events.list", hidden=True),
        NavNode("events.exposure", "Exposure", "/showcase/events", parent="events.event",
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
        NavNode("locations", "Locations", "/showcase/locations", icon="showcase:map",
                keywords="exposure portfolio map draw search",
                description="The exposure snapshot, searched on the map"),
        NavNode("grids", "Grids", "/showcase/items", icon="queue", keywords="list table",
                description="Items, record pages, forms and a live-updating grid"),
        NavNode("grids.items", "Items", "/showcase/items", parent="grids",
                description="Every column kind, filters, views, bulk actions"),
        NavNode("grids.new", "New item", "/showcase/items/new", parent="grids",
                keywords="create add form", permission=items.EDIT),
        NavNode("grids.item", "Item", "/showcase/items", parent="grids.items", hidden=True),
        NavNode("grids.jobs", "Live updates", "/showcase/jobs", parent="grids",
                keywords="jobs polling background", description="A grid that refreshes itself"),
        NavNode("inbox", "Reading pane", "/showcase/inbox", icon="inbox",
                keywords="mail email messages split", description="Split list and reading pane"),
        NavNode("inbox.inbox", "Inbox", "/showcase/inbox", parent="inbox"),
        NavNode("inbox.starred", "Starred", "/showcase/inbox?view=starred", parent="inbox"),
        NavNode("inbox.archive", "Archive", "/showcase/inbox?view=archive", parent="inbox"),
        NavNode("charts", "Charts", "/showcase/charts", icon="showcase:chart",
                keywords="chart graph dashboard map treemap sankey calendar",
                description="Every chart kind, linked to a grid"),
        NavNode("forms", "Forms", "/showcase/specs", icon="showcase:form",
                keywords="json schema document", description="Forms from JSON Schema"),
        NavNode("forms.specs", "Specs", "/showcase/specs", parent="forms",
                description="Documents edited with a schema form"),
        NavNode("forms.new", "New spec", "/showcase/specs/new", parent="forms",
                permission=specs.EDIT),
        NavNode("forms.spec", "Spec", "/showcase/specs", parent="forms.specs", hidden=True),
        NavNode("forms.freeform", "Free-form", "/showcase/freeform", parent="forms",
                description="A form inferred from the document"),
        NavNode("flows", "Flows", "/showcase/flows", icon="showcase:flow",
                keywords="stepper tree graph dag dependencies",
                description="Stepper, tree and graph"),
    ],
)
