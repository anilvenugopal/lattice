"""Charts: every chart kind on the Items grid, linked to its view, filters and search."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from lattice.api import (
    Avg,
    ChartSpec,
    Count,
    Db,
    Sum,
    Threshold,
    Time,
    build_chart,
    build_grid,
    get_db,
    render_page,
)
from lattice_showcase.items import GRID

CHARTS = [
    ChartSpec("showcase.by_week", "Created per week, by status", GRID, "bar",
              x=Time("created_at", "week"), series="status", stacked=True,
              thresholds=[Threshold(12, "Weekly target", "accent")]),
    ChartSpec("showcase.amount_by_month", "Amount per month", GRID, "area",
              x=Time("created_at", "month"), y=Sum("amount", "Amount"), format="money"),
    ChartSpec("showcase.by_status", "Items by status", GRID, "doughnut", x="status"),
    ChartSpec("showcase.by_category", "Amount by category", GRID, "bar", x="category",
              y=Sum("amount", "Amount"), format="money", horizontal=True),
    ChartSpec("showcase.calendar", "Updates per day", GRID, "calendar",
              x=Time("updated_at", "day"), height=200),
    ChartSpec("showcase.treemap", "Amount by category and status", GRID, "treemap",
              x="category", series="status", y=Sum("amount", "Amount"), format="money"),
    ChartSpec("showcase.flow", "Category to status", GRID, "sankey", x="category",
              series="status"),
    ChartSpec("showcase.map", "Items by country", GRID, "choropleth", x="country", height=320),
    ChartSpec("showcase.score", "Average score per month, by priority", GRID, "line",
              x=Time("created_at", "month"), y=Avg("score", "Score"), series="priority",
              format="percent"),
    ChartSpec("showcase.owners", "Open items per owner", GRID, "bar", x="owner", y=Count("Items"),
              limit=8),
]

router = APIRouter()


@router.get("/charts")
def charts_page(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "showcase/charts.html", "charts",
                       grid=build_grid(request, db, GRID),
                       charts=[build_chart(request, c) for c in CHARTS])
