"""Account › Notifications: the signed-in user's inbox, the bell's count, and following
records (ADR 0016). The kernel service is lattice/kernel/services/notifications.py."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from lattice.components.grid import (
    Action,
    ActionContext,
    Column,
    GridSpec,
    View,
    render_grid_page,
)
from lattice.components.references import resolve
from lattice.components.tiles import HomeTile
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user
from lattice.kernel.database import Db, get_db, transaction
from lattice.kernel.queries import SQL
from lattice.kernel.services import notifications
from lattice.kernel.web import render, toast

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(csrf_protect)])


def mark_read(ctx: ActionContext) -> str:
    ctx.db.run(SQL.notifications.mark_read, ids=ctx.ids, user_id=ctx.user.id)
    return f"Marked {ctx.count} read."


def mark_all_read(ctx: ActionContext) -> str:
    ctx.db.run(SQL.notifications.mark_all_read, user_id=ctx.user.id)
    return "Marked everything read."


def dismiss(ctx: ActionContext) -> str:
    ctx.db.run(SQL.notifications.dismiss, ids=ctx.ids, user_id=ctx.user.id)
    return f"Dismissed {ctx.count}."


GRID = GridSpec(
    key="notifications", title="Notifications", path="/account/notifications",
    query=SQL.notifications.grid,
    columns=[Column("title", "Notification", kind="strong", secondary="body", required=True),
             Column("subject", "About", kind="template", template="account/notification_subject.html",
                    sortable=False, width="220px"),
             Column("count", "Times", kind="number", align="right", width="70px"),
             Column("created_at", "When", kind="ago", width="110px")],
    search=["title", "body"],
    views=[View("unread", "Unread", where={"done": False}), View("all", "All")],
    actions=[Action("read_all", "Mark all read", scope="none", handler=mark_all_read, icon="check"),
             Action("read", "Mark read", handler=mark_read, icon="check", when={"done": [False]}),
             Action("dismiss", "Dismiss", handler=dismiss, icon="x")],
    row_class=lambda row: "" if row["done"] else "is-unread",
    default_sort="-created_at", row_href="/account/notifications/{id}",
    empty_title="Nothing to tell you", empty_text="Follow a record to hear about changes to it.",
)
TILES = [HomeTile("Unread notifications", GRID, view="unread", tone="info")]


@router.get("/notifications")
def notifications_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "account.notifications",
                            subtitle="What you have been told about, newest first.")


@router.get("/notifications/badge")
def badge(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    """The bell's unread count, polled by the top bar."""
    return render(request, "account/notification_badge.html", count=notifications.unread(db, user.id))


@router.get("/notifications/{notification_id}")
def open_notification(notification_id: int, db: Db = Depends(get_db), user=Depends(current_user)):
    """Mark it read and go to what it is about, if the user may still see it."""
    row = db.first(SQL.notifications.open, id=notification_id, user_id=user.id)
    found = resolve(db, user, row["subject"]) if row and row["subject"] else None
    return RedirectResponse(found.url if found and found.url else "/account/notifications",
                            status_code=303)


@router.post("/follow")
def toggle_follow(request: Request, subject: str = Form(...), db: Db = Depends(get_db),
                  user=Depends(current_user)):
    """Follow or stop following a record; returns the button in its new state."""
    if resolve(db, user, subject) is None:
        return Response(status_code=404, headers=toast("That record is not available.", "danger"))
    now = not notifications.following(db, user.id, subject)
    if now:
        notifications.follow(db, user.id, subject)
    else:
        notifications.unfollow(db, user.id, subject)
    return render(request, "account/follow_button.html", subject=subject, following=now,
                  headers=toast("Following: you will be told about changes." if now
                                else "No longer following."))


async def background() -> None:
    """Started with the host: delete notifications past their retention, hourly."""
    def expire() -> None:
        with transaction() as db:
            notifications.expire(db)
    while True:
        try:
            await run_in_threadpool(expire)
        except Exception:
            log.exception("Expiring notifications failed")
        await asyncio.sleep(3600)
