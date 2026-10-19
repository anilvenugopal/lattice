"""Inbox: a per-user mailbox in a split layout (list + reading pane).

Shows row scoping in the query (each user sees only their messages), an inline
star toggle, row styling for unread rows, and folder views driven from the sidebar.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from lattice.api import (
    Action,
    ActionResult,
    Column,
    Db,
    Filter,
    GridSpec,
    HomeTile,
    Palette,
    View,
    csrf_protect,
    get_db,
    render_grid_page,
    sql_queries,
)

SQL = sql_queries(Path(__file__).parent / "sql").inbox


def mark_read(ctx):
    ctx.db.run(SQL.set_read, ids=ctx.ids, is_read=True)
    return ActionResult(f"Marked {ctx.count} read.", clear_selection=False)


def mark_unread(ctx):
    ctx.db.run(SQL.set_read, ids=ctx.ids, is_read=False)
    return ActionResult(f"Marked {ctx.count} unread.", clear_selection=False)


def toggle_star(ctx):
    starred = sum(1 for r in ctx.rows if r["is_starred"])
    # Star all unless every selected message is already starred.
    value = starred < ctx.count
    ctx.db.run(SQL.set_starred, ids=ctx.ids, is_starred=value)
    return ActionResult("Starred." if value else "Star removed.", clear_selection=False)


def archive(ctx):
    ctx.db.run(SQL.move, ids=ctx.ids, folder="archive")
    return f"Archived {ctx.count} message(s)."


def move_to_inbox(ctx):
    ctx.db.run(SQL.move, ids=ctx.ids, folder="inbox")
    return f"Moved {ctx.count} message(s) to Inbox."


def remove(ctx):
    ctx.db.run(SQL.delete, ids=ctx.ids)
    return f"Deleted {ctx.count} message(s)."


def panel(db: Db, user, row: dict) -> dict:
    """Opening a message marks it read; the grid then refreshes to show it."""
    message = db.one(SQL.by_id, id=row["id"])
    if not message["is_read"]:
        db.run(SQL.set_read, ids=[row["id"]], is_read=True)
    return {"template": "showcase/message_panel.html", "message": message,
            "refresh_grid": not message["is_read"]}


LABELS = [("finance", "Finance"), ("ops", "Operations"), ("customer", "Customer"),
          ("internal", "Internal")]

GRID = GridSpec(
    key="showcase.inbox",
    title="Inbox",
    path="/showcase/inbox",
    query=SQL.grid,
    columns=[
        Column("is_starred", "", kind="star", star_action="star", sortable=False, width="34px",
               required=True),
        Column("sender_name", "Message", kind="template", template="showcase/message_cell.html",
               required=True),
        Column("received_at", "Received", kind="ago", width="110px", align="right"),
    ],
    search=["sender_name", "sender_email", "subject", "snippet", "labels"],
    filters=[Filter("labels", "Label", LABELS),
             Filter("is_read", "Read", [("false", "Unread"), ("true", "Read")], multiple=False)],
    views=[
        View("inbox", "Inbox", where={"folder": "inbox"}),
        View("starred", "Starred", where={"is_starred": True}),
        View("archive", "Archive", where={"folder": "archive"}),
    ],
    actions=[
        Action("read", "Mark read", handler=mark_read, icon="mail-open",
               when={"is_read": [False]}),
        Action("unread", "Mark unread", handler=mark_unread, icon="mail",
               when={"is_read": [True]}),
        Action("star", "Star", handler=toggle_star, icon="star"),
        Action("archive", "Archive", handler=archive, icon="archive", when={"folder": ["inbox"]}),
        Action("move_inbox", "Move to Inbox", handler=move_to_inbox, icon="inbox",
               when={"folder": ["archive"]}),
        Action("delete", "Delete", handler=remove, icon="trash", tone="danger",
               confirm="Delete {count} message(s)?"),
    ],
    default_sort="-received_at",
    layout="split",
    panel=panel,
    panel_title="{subject}",
    row_class=lambda r: "" if r["is_read"] else "is-unread",
    export=False,
    search_placeholder="Search mail",
    empty_title="No messages",
    empty_text="Messages in this folder will appear here.",
    palette=Palette(title="{subject}", subtitle="{sender_name}",
                    href="/showcase/inbox?view=inbox&q={subject}", icon="mail"),
)

TILES = [
    HomeTile("Unread messages", GRID, view="inbox", filters={"is_read": ["false"]}),
]

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/inbox")
def inbox_page(request: Request, db: Db = Depends(get_db)):
    view = request.query_params.get("view") or "inbox"
    nav_key = f"inbox.{view}" if view in ("inbox", "starred", "archive") else "inbox.inbox"
    return render_grid_page(request, db, GRID, nav_key, views_in_nav=True,
                            title=dict(inbox="Inbox", starred="Starred",
                                       archive="Archive").get(view, "Inbox"))
