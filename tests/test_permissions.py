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
from lattice.testing import current, login, make_user

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


def test_lattice_declares_its_permissions():
    create_app(apps=[])
    assert sorted(permissions.CATALOGUE) == [
        "lattice.audit.view", "lattice.email.view", "lattice.roles.manage", "lattice.sessions.manage",
        "lattice.system.view", "lattice.users.manage", "lattice.views.share",
        "lattice.webhooks.manage"]


def test_defaults_are_granted_once_and_never_again(db):
    editor = [r["permission"] for r in db.all(CHECK.role_permissions, role="editor")]
    assert editor == ["lattice.views.share", "notes.edit"]
    assert db.all(CHECK.role_permissions, role="admin") == []      # admin has all, implicitly
    db.run(CHECK.take_permission, role="editor", permission="notes.edit")
    create_app(apps=[notes_app(EDIT)])
    assert permissions.sync(db) == []                              # already known: not re-granted
    editor = [r["permission"] for r in db.all(CHECK.role_permissions, role="editor")]
    assert editor == ["lattice.views.share"]


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


def test_an_auditor_sees_only_the_audit_log(db, users):
    db.run(CHECK.add_role, code="auditor", label="Auditor")
    db.run(CHECK.grant_permission, role="auditor", permission="lattice.audit.view")
    make_user(db, "audrey@test.io", roles=("auditor",))
    with TestClient(create_app(apps=[])) as c:
        login(c, "audrey@test.io")
        assert c.get("/admin/audit").status_code == 200
        for refused in ("/admin/users", "/admin/roles", "/admin/sessions", "/admin/system",
                        "/_grid/users/rows"):
            assert c.get(refused).status_code == 403, refused
        page = c.get("/admin/audit").text
        assert 'class="rail__btn is-active" href="/admin/audit"' in page   # the icon leads here
        assert 'href="/admin/users"' not in page and ">Audit log<" in page
        assert "Recent activity" in c.get("/").text                        # lattice.audit.view


def test_without_any_administration_permission_there_is_no_administration(as_user):
    page = as_user("editor").get("/").text
    assert 'aria-label="Administration"' not in page and "Recent activity" not in page
