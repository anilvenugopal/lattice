"""Administration › Webhooks: register addresses that receive events, test them, and see
every post (ADR 0016, phase 3). The kernel service is lattice/kernel/services/webhooks.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from lattice.components.grid import (
    Action,
    ActionContext,
    ActionResult,
    Column,
    Field,
    GridSpec,
    View,
    build_grid,
)
from lattice.kernel import events
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import require
from lattice.kernel.database import Db, get_db
from lattice.kernel.queries import SQL
from lattice.kernel.services import audit, webhooks
from lattice.kernel.web import render_page

MANAGE = "lattice.webhooks.manage"
TEST_EVENT = "lattice.webhook_test"


def _event_options(db, user) -> list[tuple[str, str]]:
    return [("*", "Every event"), *((t, t) for t in sorted(events.PUBLISHED))]


def create(ctx: ActionContext) -> ActionResult:
    try:
        url = webhooks.check_url(ctx.values["url"])
    except ValueError as exc:
        return ActionResult(str(exc), tone="danger")
    name = ctx.values["name"].strip()[:128]
    hook_id = ctx.db.value(SQL.webhooks.create, name=name, url=url, secret=webhooks.new_secret(),
                           events=[ctx.values["events"]], format=ctx.values["format"],
                           created_by=ctx.user.id)
    audit.record(ctx.db, ctx.user.id, "webhooks.created", f"Added webhook {name}", "webhooks", hook_id)
    return ActionResult(f"Webhook {name!r} added. Open it for its signing secret.")


def test(ctx: ActionContext) -> str:
    """Queue a test event for the selected webhooks, whatever events they take."""
    for row in ctx.rows:
        event = events.CloudEvent(type=TEST_EVENT, source=f"/lattice/{events.host_name()}/admin",
                                  time=datetime.now(UTC), data={"message": "Test from Lattice"})
        ctx.db.run(SQL.webhooks.queue, webhook_id=row["id"], event_id=str(uuid.uuid4()),
                   event_type=event.type, subject="", body=webhooks.body_for(event, row["format"]))
    return f"Test queued to {ctx.count} webhook(s); it is posted within 30 seconds."


def set_active(active: bool):
    def handler(ctx: ActionContext) -> str:
        ctx.db.run(SQL.webhooks.set_active, ids=ctx.ids, active=active)
        return f"{'Turned on' if active else 'Turned off'} {ctx.count} webhook(s)."
    return handler


def delete(ctx: ActionContext) -> str:
    ctx.db.run(SQL.webhooks.delete, ids=ctx.ids)
    return f"Deleted {ctx.count} webhook(s) and their deliveries."


def retry(ctx: ActionContext) -> str:
    ctx.db.run(SQL.webhooks.retry, ids=ctx.ids)
    return f"Queued {ctx.count} again."


WEBHOOKS = GridSpec(
    key="webhooks", title="Webhooks", path="/admin/webhooks", query=SQL.webhooks.grid,
    permission=MANAGE,
    columns=[Column("name", "Webhook", kind="strong", secondary="url", required=True),
             Column("events_text", "Events", kind="mono", width="200px"),
             Column("format", "Format", labels=dict(webhooks.FORMATS), width="220px"),
             Column("active", "On", kind="bool", width="60px"),
             Column("last_status", "Last post", kind="badge", width="110px",
                    labels={"queued": "Queued", "delivered": "Delivered", "failed": "Failed"},
                    tones={"queued": "info", "delivered": "success", "failed": "danger"}),
             Column("last_at", "When", kind="ago", width="110px")],
    search=["name", "url"],
    actions=[Action("new", "Add webhook", scope="none", handler=create, icon="plus", tone="primary",
                    fields=[Field("name", "Name", required=True, placeholder="Ops channel"),
                            Field("url", "Address", required=True, placeholder="https://hooks.example.com/…"),
                            Field("events", "Events", kind="select", required=True, default="*",
                                  options=_event_options),
                            Field("format", "Format", kind="select", required=True,
                                  default="cloudevents", options=webhooks.FORMATS)]),
             Action("test", "Send test", handler=test, icon="play"),
             Action("off", "Turn off", handler=set_active(False), icon="stop", when={"active": [True]}),
             Action("on", "Turn on", handler=set_active(True), icon="play", when={"active": [False]}),
             Action("delete", "Delete", handler=delete, icon="trash", tone="danger",
                    confirm="Delete {count} webhook(s) and every delivery to them?")],
    panel=lambda db, user, row: {"template": "admin/webhook_panel.html"},
    panel_title="{name}", default_sort="name", export=False,
    empty_title="No webhooks", empty_text="Add one to post events to Slack, Teams or another system.",
)
DELIVERIES = GridSpec(
    key="webhook_deliveries", title="Deliveries", path="/admin/webhooks",
    query=SQL.webhooks.deliveries, permission=MANAGE, poll_seconds=10,
    columns=[Column("event_type", "Event", kind="mono", secondary="webhook", required=True),
             Column("status", "Status", kind="badge", width="100px",
                    labels={"queued": "Queued", "delivered": "Delivered", "failed": "Failed"},
                    tones={"queued": "info", "delivered": "success", "failed": "danger"}),
             Column("response_status", "Answer", kind="number", align="right", width="80px"),
             Column("attempts", "Tries", kind="number", align="right", width="70px"),
             Column("created_at", "Queued", kind="ago", width="110px"),
             Column("delivered_at", "Delivered", kind="ago", width="110px")],
    search=["event_type", "webhook"],
    views=[View("all", "All"), View("failed", "Failed", where={"status": "failed"})],
    actions=[Action("retry", "Retry", handler=retry, icon="retry", when={"status": ["failed"]})],
    panel=lambda db, user, row: {"template": "admin/webhook_delivery_panel.html"},
    panel_title="{event_type}", default_sort="-created_at", export=False,
    empty_title="Nothing posted yet", empty_text="Posts appear here as events happen.",
)

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/webhooks", dependencies=[Depends(require(MANAGE))])
def webhooks_page(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "admin/webhooks.html", "admin.webhooks",
                       hooks=build_grid(request, db, WEBHOOKS),
                       deliveries=build_grid(request, db, DELIVERIES, sync_url=False))
