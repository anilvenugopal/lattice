"""Jobs: background job runs with live status.

Shows a polling grid, row-state rules on actions (`when`), and a toolbar action
that collects input and creates a row. The template has no job runner; in
development `simulate()` advances queued and running jobs so the grid moves.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from lattice.api import (
    Action,
    ActionContext,
    ActionResult,
    Column,
    Field,
    Filter,
    GridSpec,
    HomeTile,
    Palette,
    SessionLocal,
    User,
    View,
    csrf_protect,
    get_db,
    render_grid_page,
    settings,
    utcnow,
)
from lattice_demo.models import Job

STATUSES = [("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"),
            ("failed", "Failed"), ("cancelled", "Cancelled")]
STATUS_TONES = {"queued": "neutral", "running": "info", "succeeded": "success",
                "failed": "danger", "cancelled": "warning"}
JOB_TYPES = [("import", "Import"), ("export", "Export"), ("sync", "Sync"),
             ("report", "Report"), ("cleanup", "Cleanup")]
ACTIVE = ["queued", "running"]

log = logging.getLogger(__name__)


def query(db: Session, user):
    return (
        select(Job.id, Job.name, Job.job_type, Job.status, Job.progress, Job.attempts,
               Job.error, User.display_name.label("submitted_by"), Job.created_at,
               Job.started_at, Job.finished_at)
        .outerjoin(User, User.id == Job.submitted_by)
    )


def create_job(ctx: ActionContext) -> ActionResult:
    job = Job(name=ctx.values["name"], job_type=ctx.values.get("job_type") or "sync",
              submitted_by=ctx.user.id)
    ctx.db.add(job)
    ctx.db.flush()
    return ActionResult(f"Queued job #{job.id}.")


def retry(ctx: ActionContext) -> str:
    ctx.db.execute(update(Job).where(Job.id.in_(ctx.ids)).values(
        status="queued", progress=0, error="", started_at=None, finished_at=None,
        attempts=Job.attempts + 1))
    return f"Re-queued {ctx.count} job(s)."


def cancel(ctx: ActionContext) -> str:
    ctx.db.execute(update(Job).where(Job.id.in_(ctx.ids)).values(
        status="cancelled", finished_at=utcnow()))
    return f"Cancelled {ctx.count} job(s)."


def panel(db: Session, user, row: dict) -> dict:
    duration = None
    if row["started_at"]:
        duration = (row["finished_at"] or utcnow()) - row["started_at"]
    return {"template": "demo/job_panel.html", "duration": duration}


GRID = GridSpec(
    key="demo.jobs",
    title="Jobs",
    path="/demo/jobs",
    query=query,
    columns=[
        Column("id", "#", kind="mono", width="70px", required=True),
        Column("name", "Job", kind="strong", secondary="job_type", required=True),
        Column("job_type", "Type", labels=dict(JOB_TYPES), hidden=True),
        Column("status", "Status", kind="badge", tones=STATUS_TONES, labels=dict(STATUSES),
               width="120px"),
        Column("progress", "Progress", kind="progress", width="150px"),
        Column("attempts", "Attempts", kind="number", align="right", width="90px", hidden=True),
        Column("submitted_by", "Submitted by", kind="user", width="170px"),
        Column("created_at", "Created", kind="ago", width="130px"),
        Column("finished_at", "Finished", kind="ago", width="130px"),
    ],
    search=["name", "job_type", "submitted_by", "error"],
    filters=[Filter("status", "Status", STATUSES), Filter("job_type", "Type", JOB_TYPES)],
    views=[
        View("all", "All"),
        View("active", "Active", where={"status": ACTIVE}),
        View("failed", "Failed", where={"status": "failed"}),
        View("done", "Succeeded", where={"status": "succeeded"}),
    ],
    actions=[
        Action("new", "Run job", scope="none", handler=create_job, tone="primary", icon="play",
               fields=[Field("name", "Name", required=True, placeholder="Nightly sync"),
                       Field("job_type", "Type", kind="select", options=JOB_TYPES,
                             default="sync")]),
        Action("retry", "Retry", handler=retry, icon="retry",
               when={"status": ["failed", "cancelled"]}),
        Action("cancel", "Cancel", handler=cancel, icon="stop", tone="danger",
               when={"status": ACTIVE}, confirm="Cancel {count} job(s)?"),
    ],
    default_sort="-created_at",
    panel=panel,
    panel_title="#{id} · {name}",
    poll_seconds=5,
    search_placeholder="Search jobs, types, errors",
    empty_title="No jobs",
    palette=Palette(title="Job #{id} · {name}", subtitle="{status}", href="/demo/jobs?q={name}",
                    icon="activity"),
)

TILES = [
    HomeTile("Jobs running", GRID, view="active", tone="info"),
    HomeTile("Jobs failed", GRID, view="failed", tone="danger"),
]

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/jobs")
def jobs_page(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, GRID, "jobs",
                            subtitle="Background work. The list refreshes every 5 seconds.")


async def background() -> None:
    """Started by the host (AppManifest.background). In development, moves demo jobs along every 3s."""
    if settings.app_env != "development":
        return

    def tick():
        with SessionLocal() as db:
            simulate(db)

    while True:
        await asyncio.sleep(3)
        try:
            await run_in_threadpool(tick)
        except Exception:  # keep the demo loop alive; failures are logged
            log.exception("job simulation tick failed")


def simulate(db: Session) -> None:
    """Development only: move queued jobs to running and running jobs toward done."""
    now = utcnow()
    for job in db.scalars(select(Job).where(Job.status.in_(ACTIVE))).all():
        if job.status == "queued":
            job.status, job.started_at = "running", now
        else:
            job.progress = min(100, job.progress + random.randint(5, 25))
            if job.progress >= 100:
                job.status, job.finished_at = "succeeded", now
            elif random.random() < 0.03:
                job.status, job.finished_at = "failed", now
                job.error = "TimeoutError: upstream service did not respond within 30s"
        if job.started_at and now - job.started_at > timedelta(hours=1):
            job.status, job.finished_at = "failed", now
    db.commit()
