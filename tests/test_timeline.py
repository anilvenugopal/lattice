"""Timelines (ADR 0014): bars in lanes from a grid's rows, windowed on the server."""

import pytest
from fastapi import APIRouter, Request

from lattice.api import AppManifest, TimelineSpec, build_timeline
from lattice.host import AppError, create_app
from lattice.kernel.services import audit
from lattice.platform.admin import AUDIT

EVENTS = TimelineSpec("stats.events", "Events", AUDIT, start="at", lane="action",
                      label="{action} {target_id}", href="/admin/audit")
router = APIRouter()


@router.get("/page")
def page(request: Request):
    return build_timeline(request, EVENTS, fixed={"target_type": "doc"})["config"]


@pytest.fixture
def host_apps():
    return [AppManifest(key="stats", label="Stats", routers=[router], timelines=[EVENTS])]


@pytest.fixture
def events(db, users):
    for action, n in (("doc.created", 3), ("doc.signed", 2)):
        for i in range(n):
            audit.record(db, users["admin"].id, action, "x", "doc", i)


def test_lanes_and_bars_come_from_the_grids_rows(as_user, events):
    data = as_user("admin").get("/_timeline/stats.events/data?f_target_type=doc").json()
    assert [lane["key"] for lane in data["lanes"]] == ["doc.created", "doc.signed"]
    assert len(data["bars"]) == 5 and all(b["marker"] for b in data["bars"])   # no end column
    bar = data["bars"][0]
    assert bar["start"].endswith("Z") and bar["href"] == "/admin/audit"
    assert bar["label"] == "doc.created 0"
    assert data["extent"]["from"] <= bar["start"] <= data["extent"]["to"]
    assert not data["truncated"]


def test_the_window_narrows_on_the_server(as_user, events):
    c = as_user("admin")
    data = c.get("/_timeline/stats.events/data").json()
    later = data["extent"]["to"].replace("Z", "+00:00")
    empty = c.get("/_timeline/stats.events/data", params={"from": "2001-01-01T00:00:00Z",
                                                          "to": "2001-01-02T00:00:00Z"}).json()
    assert empty["bars"] == [] and empty["window"]["from"] == "2001-01-01T00:00:00Z"
    assert c.get("/_timeline/stats.events/data", params={"from": later}).status_code == 400
    assert c.get("/_timeline/stats.events/data", params={"from": "x", "to": "y"}).status_code == 400


def test_timelines_need_the_grids_permission(as_user, events):
    assert as_user("editor").get("/_timeline/stats.events/data").status_code == 403
    assert as_user("admin").get("/_timeline/nope/data").status_code == 404


def test_build_timeline_passes_fixed_and_linked_state(as_user, events):
    config = as_user("admin").get("/stats/page?q=x&sort=at").json()
    assert config["params"] == "q=x&x_target_type=doc" and config["fixed"] == "x_target_type=doc"
    assert config["grid"] == "audit"


def test_a_timeline_outside_its_namespace_stops_the_host():
    bad = TimelineSpec("other.events", "E", AUDIT, start="at", lane="action")
    with pytest.raises(AppError, match="timeline key 'other.events'"):
        create_app(apps=[AppManifest(key="stats", label="Stats", timelines=[bad])])
