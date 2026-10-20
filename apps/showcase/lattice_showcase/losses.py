"""Loss estimate: a Monte Carlo simulation of what an event could cost. Illustrative.

For each of N simulated storms:

1. **Track.** The forecast track, shifted sideways by a random amount (the cone's
   uncertainty). Perils without a track use the footprint's centre.
2. **Strength.** The peak wind, scaled up or down at random.
3. **Wind at each location.** Falls off with distance from the track.
4. **Damage.** A damage ratio from that wind and the building's construction, on a simple
   curve, with random variation per location.
5. **Loss.** Damage ratio × insured value, less the deductible, summed over the locations.

The 1,000 totals give the average, the 1-in-100 and 1-in-250 losses, and the exceedance
curve. It runs as a background job; in production that is a Taskline job. It is not a
catastrophe model: the curves and spreads below are stated, simple and made up.
"""

from __future__ import annotations

import asyncio
import logging
import math
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

import geoengine
from lattice.api import (
    Action,
    ActionContext,
    ActionResult,
    ChartSpec,
    Column,
    Db,
    Field,
    GridSpec,
    Threshold,
    View,
    build_chart,
    build_grid,
    get_db,
    render_page,
    settings,
    sql_queries,
    transaction,
)
from lattice_showcase.events import MANAGE

SQL = sql_queries(Path(__file__).parent / "sql").losses
log = logging.getLogger(__name__)

ASSUMPTIONS = {
    "track_shift_sd_km": 60,          # sideways uncertainty of the track
    "wind_scale_sd": 0.12,            # spread of the peak wind, as a share
    "decay_radius_km": 110,           # wind falls to 37% of peak at this distance
    "default_peak_mph": 110,          # when the event form gives none
    "location_noise_sd": 0.35,        # spread of each location's damage
    # Wind (mph) where damage starts, and where everything is destroyed, by construction.
    "vulnerability": {"frame": [55, 170], "masonry": [65, 190], "steel": [75, 215],
                      "manufactured": [45, 140], "vehicle": [60, 200]},
}
STATUSES = [("queued", "Queued"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")]
TONES = {"queued": "neutral", "running": "info", "done": "success", "failed": "danger"}
KM_PER_DEG = 111.0


def run_estimate(ctx: ActionContext) -> ActionResult:
    event_id = int(ctx.query.fixed.get("event_id", ["0"])[0]) if ctx.query else 0
    run_id = ctx.db.value(SQL.queue, event_id=event_id, simulations=int(ctx.values["simulations"]),
                          assumptions=ASSUMPTIONS)
    if run_id is None:
        return ActionResult("This event has no footprint to estimate.", tone="warning")
    return f"Estimate #{run_id} queued: it appears below as it runs."


SAMPLES = GridSpec(
    key="showcase.loss_samples", title="Simulated losses", path="/showcase/events",
    query=SQL.samples, columns=[Column("id", "Simulation", kind="number"),
                                Column("loss", "Loss", kind="money", align="right")],
    default_sort="-loss", selection="none", export=True,
)
RUNS = GridSpec(
    key="showcase.loss_runs", title="Estimates", path="/showcase/events", query=SQL.runs,
    columns=[Column("id", "#", kind="mono", width="60px"),
             Column("footprint", "Footprint", kind="strong"),
             Column("simulations", "Storms", kind="number", align="right", width="90px"),
             Column("status", "Status", kind="badge", labels=dict(STATUSES), tones=TONES, width="100px"),
             Column("progress", "Progress", kind="progress", width="140px"),
             Column("mean_loss", "Average", kind="money", align="right", width="130px"),
             Column("p99_loss", "1 in 100", kind="money", align="right", width="130px"),
             Column("finished_at", "Finished", kind="ago", width="110px")],
    actions=[Action("run", "Run estimate", scope="none", handler=run_estimate, tone="primary",
                    icon="play", permission=MANAGE,
                    fields=[Field("simulations", "Simulated storms", kind="select", default="1000",
                                  options=[("500", "500"), ("1000", "1,000"), ("5000", "5,000")])])],
    poll_seconds=2, selection="none", default_sort="-id", views=[View("all", "All")], export=False,
    empty_title="No estimates yet", empty_text="Run one: it takes a few seconds.",
)
CHARTS = [
    ChartSpec("showcase.loss_histogram", "How often each loss came up", SAMPLES, "histogram",
              x="loss", bins=30, format="money", height=300),
    ChartSpec("showcase.loss_exceedance", "Chance the loss is more than…", SAMPLES, "exceedance",
              x="loss", format="money", height=300,
              thresholds=[Threshold(1, "1 in 100", "danger"), Threshold(0.4, "1 in 250", "warning")]),
]

router = APIRouter()


@router.get("/events/{event_id}/loss")
def loss_page(event_id: int, request: Request, db: Db = Depends(get_db)):
    from lattice_showcase.exposure import EVENTS
    fixed = {"event_id": event_id}
    return render_page(request, "showcase/loss.html", "events.loss",
                       event=db.one(EVENTS.by_id, id=event_id), latest=db.first(SQL.latest, event_id=event_id),
                       assumptions=ASSUMPTIONS, runs=build_grid(request, db, RUNS, sync_url=False, fixed=fixed),
                       charts=[build_chart(request, c, linked=False, fixed=fixed) for c in CHARTS],
                       crumb="Loss estimate")


# ── The model ────────────────────────────────────────────────────────────────

def _track(db: Db, layer: str) -> np.ndarray:
    """The forecast track as (lon, lat) points, or the footprint's centre."""
    shapes = geoengine.as_geojson(db.conn, layer)["features"]
    for f in shapes:
        if f["properties"].get("track"):
            return np.array(f["properties"]["track"], dtype=float)
    ring = np.array(shapes[0]["geometry"]["coordinates"][0], dtype=float) if shapes else np.zeros((1, 2))
    return ring.mean(axis=0, keepdims=True)


def _distance_km(points: np.ndarray, track: np.ndarray) -> np.ndarray:
    """Distance from each point to the nearest point of the track polyline, in km
    (an equirectangular approximation, fine at this scale)."""
    scale = np.array([math.cos(math.radians(float(points[:, 1].mean()))), 1.0]) * KM_PER_DEG
    p = points * scale
    t = track * scale
    if len(t) == 1:
        return np.linalg.norm(p - t[0], axis=1)
    best = np.full(len(p), np.inf)
    for a, b in zip(t[:-1], t[1:], strict=True):
        ab = b - a
        u = np.clip(((p - a) @ ab) / max(float(ab @ ab), 1e-9), 0, 1)
        best = np.minimum(best, np.linalg.norm(p - (a + u[:, None] * ab), axis=1))
    return best


def simulate(inputs: list[dict], track: np.ndarray, peak_mph: float, simulations: int,
             seed: int, assumptions: dict = ASSUMPTIONS, progress=None) -> np.ndarray:
    """Total loss per simulated storm."""
    rng = np.random.default_rng(seed)
    points = np.array([[float(r["lon"]), float(r["lat"])] for r in inputs])
    tiv = np.array([float(r["tiv"]) for r in inputs])
    deductible = np.array([float(r["deductible"]) for r in inputs])
    curves = assumptions["vulnerability"]
    lo = np.array([curves.get(r["construction"], curves["frame"])[0] for r in inputs], dtype=float)
    hi = np.array([curves.get(r["construction"], curves["frame"])[1] for r in inputs], dtype=float)
    direction = track[-1] - track[0] if len(track) > 1 else np.array([0.0, 1.0])
    normal = np.array([-direction[1], direction[0]]) / (np.linalg.norm(direction) or 1.0)
    losses = np.zeros(simulations)
    for i in range(simulations):
        shift_deg = rng.normal(0, assumptions["track_shift_sd_km"]) / KM_PER_DEG
        peak = peak_mph * rng.lognormal(0, assumptions["wind_scale_sd"])
        wind = peak * np.exp(-_distance_km(points, track + normal * shift_deg)
                             / assumptions["decay_radius_km"])
        ratio = np.clip((wind - lo) / (hi - lo), 0, 1) ** 2
        ratio = np.clip(ratio * rng.lognormal(0, assumptions["location_noise_sd"], len(points)), 0, 1)
        losses[i] = np.maximum(ratio * tiv - deductible, 0).sum()
        if progress and i % 100 == 99:
            progress(i + 1)
    return losses


def summary(losses: np.ndarray) -> dict:
    return {"mean_loss": round(float(losses.mean())),
            "p99_loss": round(float(np.quantile(losses, 0.99))),
            "p996_loss": round(float(np.quantile(losses, 0.996)))}


def estimate(db: Db, run: dict, progress=None) -> None:
    """Simulate and store one run's losses (inside the caller's transaction)."""
    peril = db.one(SQL.event_peril, footprint_id=run["footprint_id"])
    inputs = db.all(SQL.inputs, footprint_id=run["footprint_id"])
    peak = float((peril["details"] or {}).get("max_wind_mph") or ASSUMPTIONS["default_peak_mph"])
    losses = simulate(inputs, _track(db, peril["layer"]), peak, run["simulations"], seed=run["id"],
                      progress=progress)
    db.run_many(SQL.add_sample, [{"run_id": run["id"], "simulation": i + 1, "loss": round(float(v))}
                                 for i, v in enumerate(losses)])
    db.run(SQL.finish, id=run["id"], **summary(losses))


def process_next() -> bool:
    """Run the oldest queued estimate. Returns False if there was none."""
    with transaction() as db:
        run = db.first(SQL.next_queued)
    if run is None:
        return False
    def progress(done: int) -> None:
        with transaction() as db:
            db.run(SQL.progress, id=run["id"], progress=max(1, 100 * done // run["simulations"] - 1))

    with transaction() as db:
        estimate(db, run, progress)
    return True


async def background() -> None:
    """Started with the host: run queued estimates every 2 s (development only)."""
    if settings.app_env != "development":
        return
    while True:
        try:
            while await run_in_threadpool(process_next):
                pass
        except Exception:
            log.exception("Loss estimate failed")
        await asyncio.sleep(2)
