"""Every page renders for the roles that can see it."""

import pytest

from app.nav import NODES
from tests.conftest import csrf

PAGES = ["/", "/work", "/work/1", "/jobs", "/inbox", "/inbox?view=archive",
         "/account/preferences", "/account/profile", "/account/security"]
ADMIN_PAGES = ["/admin/users", "/admin/users/new", "/admin/roles", "/admin/sessions",
               "/admin/audit", "/admin/system", "/admin/ui-kit"]


@pytest.mark.parametrize("path", PAGES)
def test_viewer_pages(as_user, items, path):
    assert as_user("viewer").get(path).status_code == 200


@pytest.mark.parametrize("path", ADMIN_PAGES + PAGES)
def test_admin_pages(as_user, items, path):
    assert as_user("admin").get(path).status_code == 200


def test_every_visible_nav_route_resolves(as_user, items):
    c = as_user("admin")
    for node in NODES:
        if not node.hidden:
            assert c.get(node.route).status_code == 200, node.route


def test_editor_only_pages(as_user, items):
    assert as_user("viewer").get("/work/new").status_code == 403
    assert as_user("editor").get("/work/new").status_code == 200


def test_create_work_item_validates_and_redirects(as_user, items):
    c = as_user("editor")
    resp = c.post("/work/new", data={"title": "", "csrf_token": csrf(c)})
    assert "Title is required" in resp.text
    resp = c.post("/work/new", data={"title": "Fresh", "amount": "12", "csrf_token": csrf(c)},
                  follow_redirects=False)
    assert resp.status_code == 303
    assert "WI-00007" in c.get(resp.headers["location"]).text


def test_preferences_save_and_apply(as_user, items):
    c = as_user("viewer")
    c.post("/account/preferences", data={"theme": "dark", "density": "compact", "page_size": "25",
                                         "time_format": "absolute", "landing_page": "/jobs"},
           headers={"X-CSRF-Token": csrf(c)})
    html = c.get("/").text
    assert 'data-theme="dark"' in html and 'data-density="compact"' in html
    c.post("/account/preferences", data={"theme": "neon"}, headers={"X-CSRF-Token": csrf(c)})
    assert 'data-theme="dark"' in c.get("/").text


def test_admin_creates_user(as_user, db):
    c = as_user("admin")
    resp = c.post("/admin/users/new", data={"email": "new@test.io", "display_name": "New",
                                            "password": "StrongPass123", "roles": ["editor"],
                                            "csrf_token": csrf(c)}, follow_redirects=False)
    assert resp.status_code == 303
    c.cookies.clear()
    from tests.conftest import login
    login(c, "new@test.io", "StrongPass123")
    assert c.get("/work", follow_redirects=False).headers["location"] == "/auth/change-password"


def test_invalid_path_value_shows_error_page(as_user, items):
    resp = as_user("viewer").get("/work/abc")
    assert resp.status_code == 422 and "Invalid request" in resp.text and "<html" in resp.text


def test_work_item_validation_failure_is_400(as_user, items):
    c = as_user("editor")
    assert c.post("/work/new", data={"title": "", "csrf_token": csrf(c)}).status_code == 400
    assert c.post("/work/1/edit", data={"title": "", "csrf_token": csrf(c)}).status_code == 400


def test_admin_user_update_flashes_and_requires_name(as_user, users):
    c = as_user("admin")
    uid = users["viewer"].id
    resp = c.post(f"/admin/users/{uid}", data={"display_name": " ", "csrf_token": csrf(c)})
    assert resp.status_code == 400 and "Name is required" in resp.text
    resp = c.post(f"/admin/users/{uid}", data={"display_name": "Val", "roles": ["viewer"],
                                               "is_active": "on", "csrf_token": csrf(c)},
                  follow_redirects=False)
    assert resp.headers["location"] == f"/admin/users/{uid}"
    page = c.get(resp.headers["location"])
    assert "Changes saved." in page.text
    assert "Changes saved." not in c.get(f"/admin/users/{uid}").text   # shown once


def test_every_url_the_js_posts_to_exists():
    """Catches a route removed or renamed while static/js still posts to it."""
    import re
    from pathlib import Path

    from starlette.routing import Match

    from app.main import app
    urls = set()
    for js in Path("app/static/js").glob("*.js"):
        urls |= set(re.findall(r"app\.post\(\s*'(/[^'$`]+)'", js.read_text()))
    assert urls, "no app.post() URLs found"
    for url in urls:
        scope = {"type": "http", "path": url, "method": "POST"}
        assert any(r.matches(scope)[0] == Match.FULL for r in app.routes), url


def test_theme_button_save_keeps_other_preferences(as_user, items):
    c = as_user("viewer")
    c.post("/account/preferences", data={"density": "compact"}, headers={"X-CSRF-Token": csrf(c)})
    c.post("/account/preferences", data={"theme": "dark"}, headers={"X-CSRF-Token": csrf(c)})
    html = c.get("/").text
    assert 'data-theme="dark"' in html and 'data-density="compact"' in html


def test_preferences_page_selects_saved_page_size(as_user, items):
    c = as_user("viewer")
    c.post("/account/preferences", data={"page_size": "100"}, headers={"X-CSRF-Token": csrf(c)})
    html = c.get("/account/preferences").text
    assert '<option value="100" selected>' in html
    assert '<option value="50" selected>' not in html


def test_work_item_timeline_shows_actor_and_event(as_user, items):
    c = as_user("editor")
    from tests.conftest import post_json
    post_json(c, "/_grid/work_items/action/approve", {"ids": [items[0].id]})
    for path in (f"/work/{items[0].id}", f"/_grid/work_items/panel/{items[0].id}"):
        html = c.get(path).text
        assert "<strong>Editor</strong> Approve" in html, path


def test_profile_update_and_blank_name(as_user, users, db):
    c = as_user("viewer")
    resp = c.post("/account/profile", data={"display_name": "  "}, headers={"X-CSRF-Token": csrf(c)})
    assert resp.status_code == 400
    c.post("/account/profile", data={"display_name": "Val V"}, headers={"X-CSRF-Token": csrf(c)})
    db.expire_all()
    from app.models import User
    assert db.get(User, users["viewer"].id).display_name == "Val V"


def test_revoking_own_current_session_signs_out(as_user, users):
    c = as_user("viewer")
    page = c.get("/account/security").text
    import re
    session_id = re.search(r'/account/sessions/([0-9a-f]{64})/revoke', page).group(1)
    resp = c.post(f"/account/sessions/{session_id}/revoke", headers={"X-CSRF-Token": csrf(c)})
    assert resp.headers["HX-Redirect"] == "/auth/login"
    assert c.get("/", follow_redirects=False).status_code == 302


def test_home_links_come_from_the_nav_manifest(as_user, items):
    html = as_user("viewer").get("/").text
    assert "Live-polling grid" in html and 'href="/admin/users"' not in html


def test_brand_logo_variants_come_from_settings(client, as_user, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "brand_logo_light", "/static/brand/acme-light.svg")
    monkeypatch.setattr(settings, "brand_logo_dark", "/static/brand/acme-dark.svg")
    monkeypatch.setattr(settings, "brand_show_name", False)
    for html in (client.get("/auth/login").text, as_user("viewer").get("/").text):
        assert 'class="brand__logo brand__logo--light" src="/static/brand/acme-light.svg"' in html
        assert 'class="brand__logo brand__logo--dark" src="/static/brand/acme-dark.svg"' in html
        assert 'class="brand__name"' not in html
