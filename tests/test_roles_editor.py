"""Administration › Roles: create, edit and delete roles and their permissions."""

from pathlib import Path

from lattice.kernel.sql import sql_queries
from lattice.testing import csrf, login, make_user, post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def granted(db, role):
    return [r["permission"] for r in db.all(CHECK.role_permissions, role=role)]


def create(c, **form):
    data = {"code": "auditor", "label": "Auditor", "description": "Reads the audit log.",
            "permissions": ["lattice.audit.view"], "csrf_token": csrf(c), **form}
    return c.post("/admin/roles/new", data=data, follow_redirects=False)


def test_create_a_role_with_permissions(as_user, db):
    c = as_user("admin")
    resp = create(c)
    assert resp.status_code == 303 and resp.headers["location"] == "/admin/roles/auditor"
    assert db.one(CHECK.role, code="auditor")["label"] == "Auditor"
    assert granted(db, "auditor") == ["lattice.audit.view"]
    page = c.get("/admin/roles/auditor").text
    assert 'value="lattice.audit.view" checked' in page and "No members" in page


def test_role_codes_are_checked(as_user):
    c = as_user("admin")
    assert "lower-case letters" in create(c, code="Bad Code").text
    assert create(c, code="editor").status_code == 400
    assert "Name is required" in create(c, label="").text


def test_unknown_permissions_are_ignored(as_user, db):
    create(as_user("admin"), permissions=["lattice.audit.view", "made.up.thing"])
    assert granted(db, "auditor") == ["lattice.audit.view"]


def test_edit_a_roles_permissions_is_audited(as_user, db):
    c = as_user("admin")
    resp = c.post("/admin/roles/editor", data={
        "label": "Editor", "description": "Edits work.", "csrf_token": csrf(c),
        "permissions": ["lattice.audit.view"]}, follow_redirects=False)
    assert resp.status_code == 303
    assert granted(db, "editor") == ["lattice.audit.view"]
    detail = db.one(CHECK.audit_detail, action="role.updated")["detail"]
    assert detail == {"added": ["lattice.audit.view"], "removed": ["lattice.views.share"]}


def test_the_admin_role_is_not_edited(as_user):
    c = as_user("admin")
    assert "has every permission, always" in c.get("/admin/roles/admin").text
    resp = c.post("/admin/roles/admin", data={"label": "X", "csrf_token": csrf(c)})
    assert resp.status_code == 400


def test_only_unused_custom_roles_are_deleted(as_user, db, users):
    c = as_user("admin")
    create(c)
    create(c, code="busy", label="Busy")
    make_user(db, "b@test.io", roles=("busy",))
    body = post_json(c, "/_grid/roles/action/delete", {"ids": ["auditor", "busy", "editor"]}).json()
    assert "Deleted 1 role(s)" in body["message"] and "2 skipped" in body["message"]
    assert db.first(CHECK.role, code="auditor") is None
    assert db.first(CHECK.role, code="busy") and db.first(CHECK.role, code="editor")


def test_a_new_role_gives_its_permissions(client, db, users):
    login(client, "admin@test.io")
    create(client)
    make_user(db, "audrey@test.io", roles=("auditor",))
    client.cookies.clear()
    login(client, "audrey@test.io")
    assert client.get("/admin/audit").status_code == 200
    assert client.get("/admin/users").status_code == 403


def test_only_role_managers_edit_roles(as_user):
    c = as_user("editor")
    assert c.get("/admin/roles/new").status_code == 403
    assert create(c).status_code == 403
