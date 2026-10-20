"""Showcase pages render for the roles that can see them."""

import pytest

from lattice.kernel.nav import NODES
from lattice.testing import post_json

PAGES = ["/", "/showcase", "/showcase/events", "/showcase/claims", "/showcase/claims/1",
         "/showcase/notices", "/showcase/intake", "/showcase/field-reports"]
ADMIN_PAGES = ["/admin/users"]


@pytest.mark.parametrize("path", PAGES)
def test_viewer_pages(as_user, claims, path):
    assert as_user("viewer").get(path).status_code == 200


@pytest.mark.parametrize("path", ADMIN_PAGES + PAGES)
def test_admin_pages(as_user, claims, path):
    assert as_user("admin").get(path).status_code == 200


def test_every_visible_nav_route_resolves(as_user, claims):
    c = as_user("admin")
    for node in NODES:
        if not node.hidden:
            assert c.get(node.route).status_code == 200, node.route


def test_editor_only_pages(as_user, claims):
    assert as_user("viewer").get("/showcase/events/new").status_code == 403
    assert as_user("editor").get("/showcase/events/new").status_code == 200


def test_claim_history_shows_actor_and_action(as_user, claims):
    c = as_user("editor")
    post_json(c, "/_grid/showcase.claims/action/prioritise", {"ids": [claims[1].id]})
    assert "<strong>Editor</strong> Priority" in c.get(f"/showcase/claims/{claims[1].id}").text


def test_home_links_come_from_the_nav_manifest(as_user):
    html = as_user("viewer").get("/").text
    assert "A carrier responding to catastrophes" in html and 'href="/admin/users"' not in html


def test_invalid_path_value_shows_error_page(as_user):
    resp = as_user("viewer").get("/showcase/claims/abc")
    assert resp.status_code == 422 and "Invalid request" in resp.text and "<html" in resp.text


def test_showcase_pages_are_scoped_and_load_the_showcase_stylesheet(as_user, claims):
    c = as_user("viewer")
    page = c.get("/showcase").text
    assert 'data-app="showcase"' in page and 'href="/static/showcase/showcase.css"' in page
    assert "[data-app=\"showcase\"] .showcase-card" in c.get("/static/showcase/showcase.css").text
    # Panels carry the app key too, so the Ctrl+J preview gets the app's styles.
    assert 'data-app="showcase"' in c.get(f"/_grid/showcase.claims/panel/{claims[0].id}").text
