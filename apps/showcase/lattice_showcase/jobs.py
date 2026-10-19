"""Jobs: background job runs with live status.

Shows a polling grid, row-state rules on actions (`when`), and a toolbar action
that collects input and creates a row. The template has no job runner; in
development `simulate()` advances queued and running jobs so the grid moves.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from lattice.api import (
    Action,
    ActionContext,
    ActionResult,
    Column,
    Db,
    Field,
    Filter,
    GridSpec,
    HomeTile,
    Palette,
    View,
    csrf_protect,
    get_db,
    render_grid_page,
    settings,
    sql_queries,
    transaction,
)

SQL = sql_queries(Path(__file__).parent / "sql").jobs

STATUSES = [("queued", "Queued"), ("running", "Running"), ("succeeded", "Succeeded"),
            ("failed", "Failed"), ("cancelled", "Cancelled")]
STATUS_TONES = {"queued": "neutral", "running": "info", "succeeded": "success",
                "failed": "danger", "cancelled": "warning"}
JOB_TYPES = [("import", "Import"), ("export", "Export"), ("sync", "Sync"),
             ("report", "Report"), ("cleanup", "Cleanup")]
ACTIVE = ["queued", "running"]

log = logging.getLogger(__name__)


def create_job(ctx: ActionContext) -> ActionResult:
    job_id = ctx.db.value(SQL.create, name=ctx.values["name"],
                          job_type=ctx.values.get("job_type") or "sync", submitted_by=ctx.user.id)
    return ActionResult(f"Queued job #{job_id}.")


def retry(ctx: ActionContext) -> str:
    ctx.db.run(SQL.retry, ids=ctx.ids)
    return f"Re-queued {ctx.count} job(s)."


def cancel(ctx: ActionContext) -> str:
    ctx.db.run(SQL.cancel, ids=ctx.ids)
    return f"Cancelled {ctx.count} job(s)."


def panel(db: Db, user, row: dict) -> dict:
    duration = None
    if row["started_at"]:
        now = datetime.now(UTC).replace(tzinfo=None)
        duration = (row["finished_at"] or now) - row["started_at"]
    return {"template": "showcase/job_panel.html", "duration": duration}


GRID = GridSpec(
    key="showcase.jobs",
    title="Jobs",
    path="/showcase/jobs",
    query=SQL.grid,
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
    palette=Palette(title="Job #{id} · {name}", subtitle="{status}", href="/showcase/jobs?q={name}",
                    icon="activity"),
)

TILES = [
    HomeTile("Jobs running", GRID, view="active", tone="info"),
    HomeTile("Jobs failed", GRID, view="failed", tone="danger"),
]

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/jobs")
def jobs_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "grids.jobs",
                            subtitle="Background work. The list refreshes every 5 seconds.")


async def background() -> None:
    """Started by the host (AppManifest.background). In development, moves demo jobs along every 3s."""
    if settings.app_env != "development":
        return

    def tick():
        with transaction() as db:
            simulate(db)

    while True:
        await asyncio.sleep(3)
        try:
            await run_in_threadpool(tick)
        except Exception:  # keep the demo loop alive; failures are logged
            log.exception("job simulation tick failed")


def simulate(db: Db) -> None:
    """Development only: move running jobs toward done, then start queued jobs."""
    db.run(SQL.advance_running)
    db.run(SQL.start_queued)
