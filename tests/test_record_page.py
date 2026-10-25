"""The record page: one grid row as a page, read through the grid's query, with its actions."""

from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, Request

from lattice.api import (
    AppManifest,
    Db,
    Link,
    NavNode,
    Panel,
    RecordPage,
    get_db,
    render_record_page,
)
from lattice.platform.admin import USERS
from lattice.testing import csrf

PAGE = RecordPage(
    grid=USERS, nav_key="people.person", title="{display_name}", subtitle="{email}",
    status="is_active", properties=["email", "roles", "last_login_at"],
    links=[Link("Edit", "/admin/users/{id}", icon="edit", permission="lattice.users.manage")],
    panels=[Panel("note", "About {display_name}", "people/note.html",
                  load=lambda request, db, row: {"extra": "loaded"}),
            Panel("secret", "Secret", "people/note.html", permission="lattice.audit.view",
                  place="side")])
router = APIRouter()


@router.get("/{user_id}")
def person(user_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, PAGE, user_id)


CROWDED = RecordPage(grid=USERS, nav_key="people.person", title="{display_name}",
                     links=[Link(f"Link {n}", f"/people/{{id}}/{n}") for n in range(1, 5)])


@router.get("/{user_id}/crowded")
def crowded(user_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, CROWDED, user_id)


@pytest.fixture
def host_apps():
    return [AppManifest(key="people", label="People", routers=[router],
                        templates=Path(__file__).parent / "templates",
                        nav=[NavNode("people", "People", "/people", hidden=True),
                             NavNode("people.person", "Person", "/people", parent="people",
                                     hidden=True)])]


def test_shows_header_properties_panels_and_actions(as_user, users):
    html = as_user("admin").get(f"/people/{users['viewer'].id}").text
    assert "viewer@test.io" in html                              # subtitle and property
    assert "Note for" in html and "loaded" in html               # panel with load()
    assert 'href="/admin/users/' in html and ">Edit<" in html    # link, formatted with the row
    assert 'data-action="deactivate"' in html                    # applies: the user is active
    assert 'data-action="activate"' not in html                  # does not apply
    assert 'data-action="open"' not in html                      # opens the row_href: left out
    assert "Activity" in html


def test_header_shows_three_buttons_and_the_rest_under_more(as_user, users):
    html = as_user("admin").get(f"/people/{users['viewer'].id}/crowded").text
    header, menu = html.split(">More<", 1)
    assert all(f">Link {n}<" in header for n in (1, 2, 3)) and ">Link 4<" not in header
    assert 'class="menu__item" href="/people/' in menu and ">Link 4<" in menu
    assert 'data-action="deactivate"' in menu                    # actions follow the links


def test_the_grids_permission_guards_the_page(as_user, users):
    assert as_user("editor").get(f"/people/{users['viewer'].id}").status_code == 403


def test_a_row_the_query_does_not_return_is_404(as_user):
    assert as_user("admin").get("/people/999999").status_code == 404


def test_panels_follow_permissions(as_user, users):
    admin = as_user("admin")
    admin.post("/admin/roles/editor", data={"label": "Editor", "csrf_token": csrf(admin),
                                            "permissions": ["lattice.users.manage"]})
    html = as_user("editor").get(f"/people/{users['viewer'].id}").text
    assert "Note for" in html and "Secret" not in html


def test_an_unknown_property_is_refused():
    with pytest.raises(ValueError, match="no grid column 'nope'"):
        RecordPage(grid=USERS, nav_key="x", title="x", properties=["nope"])
