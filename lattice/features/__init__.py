"""The demo app: example screens for the three grid shapes.

Work Queue (table grid, bulk actions, detail pages), Jobs (polling grid with
state-dependent actions) and Inbox (split list and reading pane).
"""

from lattice.components.manifest import AppManifest
from lattice.features import inbox, jobs, work_items
from lattice.kernel.nav import NavNode

APP = AppManifest(
    key="demo",
    label="Demo",
    routers=[work_items.router, jobs.router, inbox.router],
    grids=[work_items.GRID, jobs.GRID, inbox.GRID],
    tiles=[*work_items.TILES, *jobs.TILES, *inbox.TILES],
    background=jobs.background,
    nav=[
        NavNode("work", "Work Queue", "/demo/work", icon="queue",
                keywords="submissions cases requests tickets",
                description="Table grid with views, bulk actions, side panel and detail pages"),
        NavNode("work.items", "Items", "/demo/work", parent="work"),
        NavNode("work.new", "New item", "/demo/work/new", parent="work", keywords="create add"),
        NavNode("work.detail", "Detail", "/demo/work", parent="work.items", hidden=True),
        # Jobs has no children, so its pages render without a sidebar.
        NavNode("jobs", "Jobs", "/demo/jobs", icon="activity", keywords="tasks runs background",
                description="Live-polling grid with state-dependent actions"),
        NavNode("inbox", "Inbox", "/demo/inbox", icon="inbox", keywords="mail email messages",
                description="Split layout: message list and reading pane"),
        NavNode("inbox.inbox", "Inbox", "/demo/inbox", parent="inbox"),
        NavNode("inbox.starred", "Starred", "/demo/inbox?view=starred", parent="inbox"),
        NavNode("inbox.archive", "Archive", "/demo/inbox?view=archive", parent="inbox"),
    ],
)
