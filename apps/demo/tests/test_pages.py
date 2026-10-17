"""Demo pages render for the roles that can see them; work item forms."""

import pytest

from lattice.kernel.nav import NODES
from lattice.testing import csrf, post_json

PAGES = ["/", "/demo/work", "/demo/work/1", "/demo/jobs", "/demo/inbox", "/demo/inbox?view=archive"]
ADMIN_PAGES = ["/admin/users"]


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
    assert as_user("viewer").get("/demo/work/new").status_code == 403
    assert as_user("editor").get("/demo/work/new").status_code == 200


def test_create_work_item_validates_and_redirects(as_user, items):
    c = as_user("editor")
    resp = c.post("/demo/work/new", data={"title": "", "csrf_token": csrf(c)})
    assert "Title is required" in resp.text
    resp = c.post("/demo/work/new", data={"title": "Fresh", "amount": "12", "csrf_token": csrf(c)},
                  follow_redirects=False)
    assert resp.status_code == 303
    assert "WI-00007" in c.get(resp.headers["location"]).text


def test_work_item_validation_failure_is_400(as_user, items):
    c = as_user("editor")
    assert c.post("/demo/work/new", data={"title": "", "csrf_token": csrf(c)}).status_code == 400
    assert c.post("/demo/work/1/edit", data={"title": "", "csrf_token": csrf(c)}).status_code == 400


def test_work_item_timeline_shows_actor_and_event(as_user, items):
    c = as_user("editor")
    post_json(c, "/_grid/demo.work_items/action/approve", {"ids": [items[0].id]})
    for path in (f"/demo/work/{items[0].id}", f"/_grid/demo.work_items/panel/{items[0].id}"):
        html = c.get(path).text
        assert "<strong>Editor</strong> Approve" in html, path


def test_home_links_come_from_the_nav_manifest(as_user, items):
    html = as_user("viewer").get("/").text
    assert "Live-polling grid" in html and 'href="/admin/users"' not in html


def test_invalid_path_value_shows_error_page(as_user, items):
    resp = as_user("viewer").get("/demo/work/abc")
    assert resp.status_code == 422 and "Invalid request" in resp.text and "<html" in resp.text


def test_demo_pages_are_scoped_and_load_the_demo_stylesheet(as_user, items):
    c = as_user("viewer")
    page = c.get("/demo/inbox").text
    assert 'data-app="demo"' in page and 'href="/static/demo/demo.css"' in page
    assert "[data-app=\"demo\"] .msg" in c.get("/static/demo/demo.css").text
    # Panels carry the app key too, so the Ctrl+J preview gets the app's styles.
    assert 'data-app="demo"' in c.get(f"/_grid/demo.work_items/panel/{items[0].id}").text
