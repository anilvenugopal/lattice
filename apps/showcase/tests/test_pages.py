"""Demo pages render for the roles that can see them; work item forms."""

import pytest

from lattice.kernel.nav import NODES
from lattice.testing import csrf, post_json

PAGES = ["/", "/showcase/items", "/showcase/items/1", "/showcase/jobs", "/showcase/inbox", "/showcase/inbox?view=archive"]
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
    assert as_user("viewer").get("/showcase/items/new").status_code == 403
    assert as_user("editor").get("/showcase/items/new").status_code == 200


def test_create_item_validates_and_redirects(as_user, items):
    c = as_user("editor")
    resp = c.post("/showcase/items/new", data={"name": "", "csrf_token": csrf(c)})
    assert "Name is required" in resp.text
    resp = c.post("/showcase/items/new", data={"name": "Fresh", "amount": "12", "csrf_token": csrf(c)},
                  follow_redirects=False)
    assert resp.status_code == 303
    assert "IT-0007" in c.get(resp.headers["location"]).text


def test_item_validation_failure_is_400(as_user, items):
    c = as_user("editor")
    assert c.post("/showcase/items/new", data={"name": "", "csrf_token": csrf(c)}).status_code == 400
    assert c.post("/showcase/items/1/edit", data={"name": "", "csrf_token": csrf(c)}).status_code == 400


def test_item_timeline_shows_actor_and_event(as_user, items):
    c = as_user("editor")
    post_json(c, "/_grid/showcase.items/action/complete", {"ids": [items[1].id]})
    for path in (f"/showcase/items/{items[1].id}", f"/_grid/showcase.items/panel/{items[1].id}"):
        html = c.get(path).text
        assert "<strong>Editor</strong> Complete" in html, path


def test_home_links_come_from_the_nav_manifest(as_user, items):
    html = as_user("viewer").get("/").text
    assert "Every Lattice component on sample data" in html and 'href="/admin/users"' not in html


def test_invalid_path_value_shows_error_page(as_user, items):
    resp = as_user("viewer").get("/showcase/items/abc")
    assert resp.status_code == 422 and "Invalid request" in resp.text and "<html" in resp.text


def test_showcase_pages_are_scoped_and_load_the_showcase_stylesheet(as_user, items):
    c = as_user("viewer")
    page = c.get("/showcase/inbox").text
    assert 'data-app="showcase"' in page and 'href="/static/showcase/showcase.css"' in page
    assert "[data-app=\"showcase\"] .msg" in c.get("/static/showcase/showcase.css").text
    # Panels carry the app key too, so the Ctrl+J preview gets the app's styles.
    assert 'data-app="showcase"' in c.get(f"/_grid/showcase.items/panel/{items[0].id}").text
