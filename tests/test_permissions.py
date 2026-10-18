"""Permissions (ADR 0009): declared by apps, granted to roles, checked by name."""

from pathlib import Path

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from lattice.components.manifest import AppManifest
from lattice.host import AppError, create_app
from lattice.kernel.auth import permissions
from lattice.kernel.auth.deps import require
from lattice.kernel.auth.permissions import Permission
from lattice.kernel.sql import sql_queries
from lattice.testing import current, login

CHECK = sql_queries(Path(__file__).parent / "sql").checks
EDIT = Permission("notes.edit", "Edit notes", "Write and change notes.", default_roles=("editor",))


def notes_app(*perms):
    router = APIRouter()

    @router.get("/write", dependencies=[Depends(require("notes.edit"))])
    def write():
        return {"ok": True}

    return AppManifest(key="notes", label="Notes", routers=[router], permissions=list(perms))


@pytest.fixture
def host_apps():
    return [notes_app(EDIT)]


@pytest.mark.parametrize("perm, message", [
    (Permission("Notes Edit", "x"), "dotted lower_case"),
    (Permission("demo.edit", "x"), "must start with 'notes.'"),
    (Permission("notes", "x"), "dotted lower_case"),
])
def test_permission_rules_stop_the_host(perm, message):
    with pytest.raises(AppError, match=message):
        create_app(apps=[notes_app(perm)])


def test_a_permission_is_declared_once():
    with pytest.raises(AppError, match="declared twice"):
        create_app(apps=[notes_app(EDIT, EDIT)])


def test_lattice_declares_one_permission_per_administration_area():
    create_app(apps=[])
    assert sorted(permissions.CATALOGUE) == [
        "lattice.audit.view", "lattice.roles.manage", "lattice.sessions.manage",
        "lattice.system.view", "lattice.users.manage"]


def test_defaults_are_granted_once_and_never_again(db):
    assert [r["permission"] for r in db.all(CHECK.role_permissions, role="editor")] == ["notes.edit"]
    assert db.all(CHECK.role_permissions, role="admin") == []      # admin has all, implicitly
    db.run(CHECK.take_permission, role="editor", permission="notes.edit")
    create_app(apps=[notes_app(EDIT)])
    assert permissions.sync(db) == []                              # already known: not re-granted
    assert db.all(CHECK.role_permissions, role="editor") == []


def test_a_permission_added_later_is_granted_its_defaults(db):
    later = Permission("notes.pin", "Pin notes", default_roles=("viewer", "nobody"))
    create_app(apps=[notes_app(EDIT, later)])
    assert permissions.sync(db) == ["notes.pin"]
    assert [r["permission"] for r in db.all(CHECK.role_permissions, role="viewer")] == ["notes.pin"]


def test_can(users):
    assert current(users["admin"]).can("anything.at.all")
    assert current(users["editor"], permissions={"notes.edit"}).can("notes.edit")
    assert not current(users["viewer"]).can("notes.edit")
    assert current(users["viewer"]).can("")                        # no permission: everyone


def test_require_on_a_route_uses_the_signed_in_users_permissions(db, users, host_apps):
    with TestClient(create_app(apps=host_apps)) as c:
        login(c, "viewer@test.io")
        assert c.get("/notes/write").status_code == 403
        c.cookies.clear()
        login(c, "editor@test.io")
        assert c.get("/notes/write").json() == {"ok": True}
        c.cookies.clear()
        login(c, "admin@test.io")
        assert c.get("/notes/write").status_code == 200
