"""Comments: comments on any record of any app, by reference (ADR 0011).

A RecordPanel shows them on every record page that names its reference kind; a grid lists
them all; `comments.added` tells the owning app about each new one, and the people
following the record are notified (ADR 0016).
"""

from pathlib import Path

from lattice.api import AppManifest, NavNode, NotificationKind
from lattice_comments import comments

HERE = Path(__file__).parent

APP = AppManifest(
    key="comments",
    label="Comments",
    icon="comments:app",
    accent="info",
    icons={"app": '<path d="M4 5h16v11H9l-5 4z"/>'},
    routers=[comments.router],
    grids=[comments.GRID],
    panels=[comments.PANEL],
    publishes=["comments.added"],
    notifications=[NotificationKind(
        "comments.on_followed", "New comment on a record you follow",
        "Someone commented on a record you follow.",
        event="comments.added", title="{author} commented", body="{excerpt}")],
    permissions=comments.PERMISSIONS,
    static=HERE / "static",
    stylesheets=["comments.css"],
    templates=HERE / "templates",
    help=HERE / "help",
    sql=HERE / "sql",
    nav=[NavNode("comments", "Comments", "/comments", icon="comments:app",
                 permission=comments.READ, keywords="discussion notes remarks",
                 description="Comments on records from every app")],
)
