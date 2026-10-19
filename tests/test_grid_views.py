"""Saved grid views: save, open, share, rename and delete."""

import pytest
from fastapi import HTTPException

from lattice.components.grid import REGISTRY, views
from lattice.testing import current, post_json


def test_save_and_list_own_view(as_user):
    c = as_user("admin")
    res = post_json(c, "/_grid/users/views", {"name": "Inactive admins",
                                               "state": "q=adm&view=inactive&page=3&bogus=1"})
    assert res.status_code == 200
    listed = c.get("/_grid/users/views").json()
    assert listed["canShare"] is True
    [view] = listed["views"]
    assert view["name"] == "Inactive admins" and view["mine"] and not view["shared"]
    assert view["state"] == "q=adm&view=inactive"          # page and unknown keys dropped


def test_state_keeps_only_valid_parts():
    spec = REGISTRY["users"]
    state = "f_is_active=false&f_nope=1&sort=-email&sort2=x&size=50&size=7&view=nope&q=+a+"
    assert views.clean_state(spec, state) == "f_is_active=false&q=a&size=50&sort=-email"


def test_duplicate_name_is_refused(as_user):
    c = as_user("admin")
    post_json(c, "/_grid/users/views", {"name": "Mine", "state": ""})
    res = post_json(c, "/_grid/users/views", {"name": "mine", "state": "q=x"})
    assert res.status_code == 400 and "already have" in res.json()["detail"]


def test_rename_resave_and_delete(as_user):
    c = as_user("admin")
    vid = post_json(c, "/_grid/users/views", {"name": "A", "state": "q=a"}).json()["id"]
    post_json(c, f"/_grid/users/views/{vid}", {"name": "B", "state": "q=b"})
    [view] = c.get("/_grid/users/views").json()["views"]
    assert (view["name"], view["state"]) == ("B", "q=b")
    assert post_json(c, f"/_grid/users/views/{vid}/delete", {}).json()["views"] == []


def test_shared_views_are_seen_by_others_but_changed_only_by_owner(db, users):
    spec = REGISTRY["users"]
    owner = current(users["editor"], permissions={views.SHARE})
    other = current(users["viewer"])
    vid = views.create(db, spec, owner, {"name": "Team", "state": "q=t", "shared": True})
    private = views.create(db, spec, owner, {"name": "Private", "state": "q=p"})
    assert [v["name"] for v in views.visible(db, spec, other)] == ["Team"]
    with pytest.raises(HTTPException) as exc:
        views.update(db, spec, other, vid, {"name": "Mine now"})
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        views.delete(db, spec, other, vid)
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException) as exc:
        views.delete(db, spec, other, private)
    assert exc.value.status_code == 404                     # not visible to them at all
    moderator = current(users["admin"], permissions={views.SHARE})
    views.delete(db, spec, moderator, vid)
    assert views.visible(db, spec, other) == []


def test_sharing_needs_the_permission(db, users):
    spec = REGISTRY["users"]
    plain = current(users["viewer"])
    with pytest.raises(HTTPException) as exc:
        views.create(db, spec, plain, {"name": "X", "state": "", "shared": True})
    assert exc.value.status_code == 403
    vid = views.create(db, spec, plain, {"name": "X", "state": ""})
    with pytest.raises(HTTPException):
        views.update(db, spec, plain, vid, {"shared": True})


def test_views_need_access_to_the_grid(as_user):
    c = as_user("viewer")
    assert c.get("/_grid/users/views").status_code == 403



def test_an_async_action_handler_is_awaited(as_user, users):
    from lattice.components.grid.spec import Action

    calls = []

    async def ping(ctx):
        calls.append(list(ctx.ids))
        return f"Pinged {ctx.count}."

    spec = REGISTRY["users"]
    spec.actions.append(Action("ping", "Ping", handler=ping))
    try:
        res = post_json(as_user("admin"), "/_grid/users/action/ping",
                        {"ids": [users["viewer"].id]})
        assert res.json()["message"] == "Pinged 1." and calls == [[users["viewer"].id]]
    finally:
        spec.actions.pop()
