"""Grid queries run under LATTICE_GRID_QUERY_TIMEOUT_SECONDS."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lattice.components.grid import Column, GridSpec, engine
from lattice.components.manifest import AppManifest
from lattice.host import create_app
from lattice.kernel.config import settings
from lattice.kernel.database import transaction
from lattice.kernel.sql import sql_queries
from lattice.testing import current, login

CHECK = sql_queries(Path(__file__).parent / "sql").checks
SLOW = GridSpec(key="notes.slow", title="Slow", path="/notes/slow", query=CHECK.slow_list,
                columns=[Column("email", "Email")])
FAST = GridSpec(key="notes.fast", title="Fast", path="/notes/fast", query=CHECK.user_list,
                columns=[Column("email", "Email")])


@pytest.fixture
def short_limit(monkeypatch):
    monkeypatch.setattr(settings, "grid_query_timeout_seconds", 0.1)


def test_a_slow_grid_query_is_cancelled_and_the_request_carries_on(db, users, short_limit):
    me = current(users["admin"])
    with transaction() as tx:
        with pytest.raises(engine.GridTimeout):
            engine.fetch_page(SLOW, tx, me, engine.GridQuery())
        assert engine.fetch_page(FAST, tx, me, engine.GridQuery()).total == 3
        assert tx.value(CHECK.statement_timeout) == "0"           # the limit is put back


def test_the_user_is_told_to_narrow_the_list(db, users, short_limit):
    web = create_app(apps=[AppManifest(key="notes", label="Notes", grids=[SLOW])])
    with TestClient(web) as c:
        login(c, "viewer@test.io")
        resp = c.get("/_grid/notes.slow/rows", headers={"HX-Request": "true"})
        assert resp.status_code == 503 and "took too long" in resp.json()["detail"]
        assert "Narrow the search" in c.get("/_grid/notes.slow/export.csv").text
