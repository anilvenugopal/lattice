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
from lattice.kernel.auth.deps import current_user, require
from lattice.kernel.config import settings
from lattice.kernel.database import Db, get_db, transaction
from lattice.kernel.queries import SQL
from lattice.kernel.services import notifications
from lattice.kernel.web import render, render_page, toast

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


@router.get("/notifications/settings")
def settings_page(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    kinds = sorted(notifications.KINDS.values(), key=lambda k: k.label)
    return render_page(request, "account/notification_settings.html", "account.notification_settings",
                       kinds=kinds, choices=notifications.choices(db, user.id),
                       channels=notifications.CHANNELS)


@router.post("/notifications/settings")
async def save_settings(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    form = await request.form()
    for key, channel in form.items():
        kind = key.removeprefix("kind:")
        if key.startswith("kind:") and kind in notifications.KINDS and channel in dict(notifications.CHANNELS):
            notifications.choose(db, user.id, kind, str(channel))
    return Response(headers=toast("Notification settings saved."))


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
    """Started with the host: every 30 seconds, queue daily summaries that are due and send
    queued emails; hourly, delete notifications past their retention."""
    def deliver() -> None:
        with transaction() as db:
            notifications.queue_digests(db)
        with transaction() as db:
            notifications.send_due(db)

    def expire() -> None:
        with transaction() as db:
            notifications.expire(db)

    ticks = 0
    while True:
        try:
            await run_in_threadpool(deliver)
            if ticks % 120 == 0:
                await run_in_threadpool(expire)
        except Exception:
            log.exception("Notification delivery failed")
        ticks += 1
        await asyncio.sleep(30)


# ── Administration › Email: every email queued, sent or logged ───────────────

EMAIL_VIEW = "lattice.email.view"
STATUSES = [("queued", "Queued"), ("sent", "Sent"), ("logged", "Logged"), ("failed", "Failed")]


def send_test(ctx: ActionContext) -> str:
    base = settings.public_url.rstrip("/")
    ctx.db.value(SQL.notifications.queue_test, user_id=ctx.user.id, to_address=ctx.user.email,
                 subject=f"Test email from {settings.app_name}",
                 body=f"This is a test of {settings.app_name}'s email.\n\n{base}")
    where = settings.smtp_host or "nowhere: no mail server is set, so it will be logged here"
    return f"Test email queued to {ctx.user.email}; it goes out within 30 seconds, to {where}."


def retry(ctx: ActionContext) -> str:
    ctx.db.run(SQL.notifications.retry_emails, ids=ctx.ids)
    return f"Queued {ctx.count} again."


EMAILS = GridSpec(
    key="emails", title="Email", path="/admin/email", query=SQL.notifications.emails,
    permission=EMAIL_VIEW,
    columns=[Column("subject", "Subject", kind="strong", secondary="to_address", required=True),
             Column("recipient", "To", kind="user", width="160px"),
             Column("kind", "Kind", labels={"notification": "Notification", "digest": "Daily summary",
                                            "test": "Test"}, width="120px"),
             Column("status", "Status", kind="badge", labels=dict(STATUSES), width="100px",
                    tones={"queued": "info", "sent": "success", "logged": "neutral", "failed": "danger"}),
             Column("attempts", "Tries", kind="number", align="right", width="70px"),
             Column("created_at", "Queued", kind="ago", width="110px"),
             Column("sent_at", "Sent", kind="ago", width="110px")],
    search=["subject", "to_address", "recipient"],
    views=[View("all", "All"), View("failed", "Failed", where={"status": "failed"})],
    actions=[Action("test", "Send me a test email", scope="none", handler=send_test, icon="mail",
                    tone="primary"),
             Action("retry", "Retry", handler=retry, icon="retry", when={"status": ["failed"]})],
    panel=lambda db, user, row: {"template": "account/email_panel.html"},
    panel_title="{subject}", default_sort="-created_at", export=False,
    empty_title="No email yet", empty_text="Emails appear here as notifications go out.",
)
admin_router = APIRouter(dependencies=[Depends(csrf_protect)])


@admin_router.get("/email", dependencies=[Depends(require(EMAIL_VIEW))])
def email_page(request: Request, db: Db = Depends(get_db)):
    note = (f"Sent through {settings.smtp_host}." if settings.smtp_host else
            "No mail server is set (LATTICE_SMTP_HOST): emails are logged here, not sent.")
    return render_grid_page(request, db, EMAILS, "admin.email", subtitle=note)
