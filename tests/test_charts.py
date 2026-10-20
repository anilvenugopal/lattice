"""Charts (ADR 0004): aggregated in the database over a grid's rows, behind its permission."""

import pytest
from fastapi import APIRouter, Request

from lattice.api import AppManifest, ChartSpec, Count, Sum, Threshold, Time, build_chart
from lattice.components.chart import router as chart_router
from lattice.host import AppError, create_app
from lattice.kernel.services import audit
from lattice.platform.admin import AUDIT

BY_ACTION = ChartSpec("stats.by_action", "Events by kind", AUDIT, "bar", x="action", limit=2)
PER_DAY = ChartSpec("stats.per_day", "Events per day", AUDIT, "line", x=Time("at", "day"),
                    series="action", thresholds=[Threshold(5, "Limit")])
router = APIRouter()


@router.get("/page")
def page(request: Request):
    return build_chart(request, BY_ACTION, fixed={"target_type": "doc"})["config"]


@pytest.fixture
def host_apps():
    return [AppManifest(key="stats", label="Stats", routers=[router], charts=[BY_ACTION, PER_DAY])]


@pytest.fixture
def events(db, users):
    for action, n in (("doc.created", 3), ("doc.signed", 2), ("doc.deleted", 1)):
        for i in range(n):
            audit.record(db, users["admin"].id, action, "x", "doc", i)
    audit.record(db, users["admin"].id, "user.created", "x", "user", 1)


def test_category_chart_keeps_the_largest_and_adds_up_the_rest(as_user, events):
    data = as_user("admin").get("/_chart/stats.by_action/data?f_target_type=doc").json()
    assert data["categories"] == ["doc.created", "doc.signed", "__other__"]
    assert sorted(data["points"]) == [["__other__", "", 1], ["doc.created", "", 3],
                                      ["doc.signed", "", 2]]
    assert data["xLabels"]["__other__"] == "Other"


def test_time_chart_groups_by_day_and_series(as_user, events):
    data = as_user("admin").get("/_chart/stats.per_day/data").json()
    assert data["x"] == {"type": "time", "unit": "day"}
    assert {p[1]: p[2] for p in data["points"]}["doc.created"] == 3
    assert data["thresholds"] == [{"value": 5, "label": "Limit", "tone": "danger"}]


def test_the_grid_search_narrows_the_chart(as_user, events):
    data = as_user("admin").get("/_chart/stats.by_action/data?q=doc.signed").json()
    assert data["points"] == [["doc.signed", "", 2]]


def test_charts_need_the_grids_permission(as_user, events):
    assert as_user("editor").get("/_chart/stats.by_action/data").status_code == 403
    assert as_user("admin").get("/_chart/nope/data").status_code == 404


def test_build_chart_passes_fixed_filters(as_user, events):
    config = as_user("admin").get("/stats/page?q=x&f_action=doc.signed&sort=at").json()
    assert config["params"] == "q=x&f_action=doc.signed&x_target_type=doc"
    assert config["fixed"] == "x_target_type=doc"
    assert config["grid"] == "audit"


def test_a_missing_column_is_a_clear_error(as_user, events):
    chart_router.register(ChartSpec("stats.bad", "Bad", AUDIT, "bar", x="action", y=Sum("nope")))
    res = as_user("admin").get("/_chart/stats.bad/data", headers={"Accept": "application/json"})
    assert res.status_code == 400 and "'nope'" in res.json()["detail"]


@pytest.mark.parametrize("chart, message", [
    (ChartSpec("other.x", "X", AUDIT, x="action"), "must start with 'stats.'"),
    (ChartSpec("stats.x", "X", AUDIT, "calendar", x="at"), "calendar needs"),
    (ChartSpec("stats.x", "X", AUDIT, "pie", x=Time("at")), "needs a column for x"),
    (ChartSpec("stats.x", "X", AUDIT, "sankey", x="action"), "needs series"),
    (ChartSpec("stats.x", "X", AUDIT, "pie", x="action", series="actor"), "has no series"),
    (ChartSpec("stats.x", "X", AUDIT, "bar", x="action", y=Count(), permission="no.such.thing"),
     "no app declares"),
])
def test_chart_rules_stop_the_host(chart, message):
    with pytest.raises(AppError, match=message):
        create_app(apps=[AppManifest(key="stats", label="Stats", charts=[chart])])


def test_histogram_and_exceedance(as_user, events, client):
    from lattice.api import ChartSpec
    hist = ChartSpec("stats.hist", "Ids", AUDIT, "histogram", x="id", bins=4)
    curve = ChartSpec("stats.curve", "Ids", AUDIT, "exceedance", x="id")
    chart_router.register(hist)
    chart_router.register(curve)
    c = as_user("admin")
    bins = c.get("/_chart/stats.hist/data?q=doc.").json()["points"]
    assert len(bins) == 4 and sum(b[2] for b in bins) == 6 and bins[0][0] < bins[-1][1]
    points = c.get("/_chart/stats.curve/data?q=doc.").json()["points"]
    assert points[0][2] == 100 and points[-1][2] == 0             # every value exceeds the minimum
    assert points[0][0] <= points[-1][0]


def test_distribution_charts_need_a_plain_numeric_x():
    with pytest.raises(AppError, match="needs a numeric column"):
        create_app(apps=[AppManifest(key="stats", label="Stats", charts=[
            ChartSpec("stats.h", "H", AUDIT, "histogram", x=Time("at"))])])


def test_a_click_narrows_by_the_charts_columns(as_user, events):
    c = as_user("admin")
    data = c.get("/_chart/stats.per_day/data").json()
    assert data["drill"] == {"x": "at", "xLabel": "When", "series": "action", "seriesLabel": "Event"}
    day = data["points"][0][0][:10]
    # A day narrows a timestamp column to that whole day.
    total = c.get("/_chart/stats.by_action/data").json()
    narrowed = c.get(f"/_chart/stats.by_action/data?x_at={day}").json()
    assert sum(p[2] for p in narrowed["points"]) == sum(p[2] for p in total["points"])   # all today
    assert c.get("/_chart/stats.by_action/data?x_at=2001-01-01").json()["points"] == []


def test_colour_mode_and_highlight_reach_the_browser(as_user, events):
    from lattice.api import Highlight
    chart_router.register(ChartSpec("stats.hot", "Hot", AUDIT, "bar", x="action",
                                    highlight=[Highlight(values=["doc.signed"], above=2)]))
    data = as_user("admin").get("/_chart/stats.hot/data").json()
    assert data["colors"] == "brand"                      # the host default
    assert data["highlight"] == [{"values": ["doc.signed"], "above": 2, "below": None,
                                  "tone": "danger"}]
    chart_router.register(ChartSpec("stats.sev", "Sev", AUDIT, "bar", x="action", colors="tones"))
    assert as_user("admin").get("/_chart/stats.sev/data").json()["colors"] == "tones"
