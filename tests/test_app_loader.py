"""create_app: app registration, mounting and the namespace rules (ADR 0003)."""

import asyncio

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import select

from lattice.components.grid import Column, GridSpec
from lattice.components.manifest import AppManifest
from lattice.host import AppError, create_app
from lattice.kernel import nav
from lattice.kernel.models import User
from lattice.testing import login


def _users_query(db, user):
    return select(User.id, User.email)


def _app(key="notes", **kw):
    return AppManifest(key=key, label=key.title(), **kw)


@pytest.mark.parametrize("manifest, message", [
    (_app("Notes"), "lowercase"),
    (_app("admin"), "reserved"),
    (_app(nav=[nav.NavNode("notes", "Notes", "/elsewhere")]), "must start with /notes"),
    (_app(grids=[GridSpec(key="list", title="L", path="/notes", query=_users_query,
                          columns=[Column("email", "Email")])]), "must start with 'notes.'"),
    (_app(grids=[GridSpec(key="notes.list", title="L", path="/other", query=_users_query,
                          columns=[Column("email", "Email")])]), "path '/other' must start"),
])
def test_loader_rejects_apps_outside_their_namespace(manifest, message):
    with pytest.raises(AppError, match=message):
        create_app(apps=[manifest])


def test_duplicate_app_keys_and_nav_keys_are_rejected():
    with pytest.raises(AppError, match="used more than once"):
        create_app(apps=[_app(), _app()])
    with pytest.raises(ValueError, match="declared twice"):
        create_app(apps=[_app(nav=[nav.NavNode("home", "Home", "/notes")])])


def test_app_routes_mount_under_its_key_and_nav_follows_app_order(db, users):
    router = APIRouter()

    @router.get("/hello")
    def hello():
        return {"ok": True}

    notes = _app(routers=[router], nav=[nav.NavNode("notes", "Notes", "/notes/hello", icon="mail")])
    web = create_app(apps=[notes])
    assert [n.key for n in nav.NODES if n.parent is None] == \
        ["home", "notes", "admin", "account"]
    assert nav.BY_KEY["notes"].app == "notes" and nav.BY_KEY["admin.users"].app == "admin"
    with TestClient(web) as c:
        assert login(c, "viewer@test.io").status_code == 303
        assert c.get("/notes/hello").json() == {"ok": True}
        assert c.get("/hello").status_code == 404


def test_background_tasks_start_and_stop(db):
    events = []

    async def loop():
        events.append("started")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            events.append("stopped")
            raise

    with TestClient(create_app(apps=[_app(background=loop)])):
        pass
    assert events == ["started", "stopped"]
