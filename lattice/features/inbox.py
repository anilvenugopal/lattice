"""Inbox: a per-user mailbox in a split layout (list + reading pane).

Shows row scoping in the query (each user sees only their messages), an inline
star toggle, row styling for unread rows, and folder views driven from the sidebar.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from lattice.components.grid import (
    Action,
    ActionContext,
    ActionResult,
    Column,
    Filter,
    GridSpec,
    Palette,
    View,
    register,
    render_grid_page,
)
from lattice.components.tiles import HomeTile, register_tile
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.db import get_db
from lattice.kernel.models import Message


def query(db: Session, user):
    return (
        select(Message.id, Message.is_starred, Message.sender_name, Message.sender_email,
               Message.subject, func.substr(Message.body, 1, 160).label("snippet"),
               Message.labels, Message.has_attachment, Message.is_read, Message.folder,
               Message.received_at)
        .where(Message.owner_id == user.id)
    )


def _set(ctx: ActionContext, **values) -> None:
    ctx.db.execute(update(Message).where(Message.id.in_(ctx.ids)).values(**values))


def mark_read(ctx):
    _set(ctx, is_read=True)
    return ActionResult(f"Marked {ctx.count} read.", clear_selection=False)


def mark_unread(ctx):
    _set(ctx, is_read=False)
    return ActionResult(f"Marked {ctx.count} unread.", clear_selection=False)


def toggle_star(ctx):
    starred = sum(1 for r in ctx.rows if r["is_starred"])
    # Star all unless every selected message is already starred.
    value = starred < ctx.count
    _set(ctx, is_starred=value)
    return ActionResult("Starred." if value else "Star removed.", clear_selection=False)


def archive(ctx):
    _set(ctx, folder="archive")
    return f"Archived {ctx.count} message(s)."


def move_to_inbox(ctx):
    _set(ctx, folder="inbox")
    return f"Moved {ctx.count} message(s) to Inbox."


def remove(ctx):
    ctx.db.execute(delete(Message).where(Message.id.in_(ctx.ids)))
    return f"Deleted {ctx.count} message(s)."


def panel(db: Session, user, row: dict) -> dict:
    msg = db.get(Message, row["id"])
    refresh = not msg.is_read
    if refresh:
        msg.is_read = True
        db.commit()
    return {"template": "features/message_panel.html", "message": msg, "refresh_grid": refresh}


LABELS = [("finance", "Finance"), ("ops", "Operations"), ("customer", "Customer"),
          ("internal", "Internal")]

GRID = register(GridSpec(
    key="inbox",
    title="Inbox",
    path="/inbox",
    query=query,
    columns=[
        Column("is_starred", "", kind="star", star_action="star", sortable=False, width="34px",
               required=True),
        Column("sender_name", "Message", kind="template", template="features/message_cell.html",
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
                    href="/inbox?view=inbox&q={subject}", icon="mail"),
))
register_tile(HomeTile("Unread messages", GRID, view="inbox", filters={"is_read": ["false"]}))


router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/inbox")
def inbox_page(request: Request, db: Session = Depends(get_db)):
    view = request.query_params.get("view") or "inbox"
    nav_key = f"inbox.{view}" if view in ("inbox", "starred", "archive") else "inbox.inbox"
    return render_grid_page(request, db, GRID, nav_key, views_in_nav=True,
                            title=dict(inbox="Inbox", starred="Starred",
                                       archive="Archive").get(view, "Inbox"))
