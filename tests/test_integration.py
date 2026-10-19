"""Working across apps (ADR 0011): URN references, record panels and CloudEvents."""

from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, HTTPException, Request

from lattice.api import (
    AppManifest,
    CloudEvent,
    Db,
    NavNode,
    RecordPage,
    RecordPanel,
    ReferenceKind,
    Resolved,
    get_db,
    parse,
    render_record_page,
    urn,
)
from lattice.components.references import BadReference, render_ref
from lattice.host import AppError, create_app
from lattice.kernel import events
from lattice.kernel.sql import sql_queries
from lattice.platform.admin import USERS
from lattice.testing import current, post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks
RECEIVED: list[CloudEvent] = []


def resolve_user(db, user, user_id):
    return Resolved(f"User {user_id}", f"/admin/users/{user_id}", badge="Active", tone="success") \
        if user_id.isdigit() and int(user_id) < 1000 else None


def record(db, event):
    RECEIVED.append(event)


def explode(db, event):
    raise RuntimeError("subscriber failed")


people = APIRouter()


@people.get("/{user_id}")
def person(user_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, PAGE, user_id)


@people.post("/shout")
def shout(db: Db = Depends(get_db), fail: bool = False):
    db.publish("people.shouted", subject=urn("people.person", 1), data={"n": 1})
    if fail:
        raise HTTPException(400, detail="rolled back")
    return {"ok": True}


PAGE = RecordPage(grid=USERS, nav_key="people", title="{display_name}",
                  reference_kind="people.person")
NOTES = RecordPanel("notes.panel", "Notes", "people/note_panel.html", kinds=["people.person"],
                    load=lambda request, db, subject: {"urn": subject.urn})


@pytest.fixture
def host_apps():
    RECEIVED.clear()
    return [
        AppManifest(key="people", label="People", routers=[people],
                    references=[ReferenceKind("people.person", "Person", resolve_user)],
                    publishes=["people.shouted"], templates=Path(__file__).parent / "templates",
                    nav=[NavNode("people", "People", "/people", hidden=True)]),
        AppManifest(key="notes", label="Notes", panels=[NOTES],
                    subscribes={"people.shouted": record}),
    ]


def test_urns():
    assert urn("showcase.item", 42) == "urn:lattice:showcase.item:42"
    ref = parse("urn:lattice:showcase.item:IT:9")
    assert (ref.kind, ref.id, ref.app) == ("showcase.item", "IT:9", "showcase")
    with pytest.raises(BadReference):
        parse("showcase.item:42")


def test_ref_renders_a_link_or_unavailable(client, db, users):
    me = current(users["viewer"])
    html = render_ref(db, me, urn("people.person", 7))
    assert 'href="/admin/users/7"' in html and "User 7" in html and "tone-success" in html
    assert "Person unavailable" in render_ref(db, me, urn("people.person", 5000))
    assert "Record unavailable" in render_ref(db, me, "urn:lattice:nobody.thing:1")


def test_other_apps_panels_join_the_record_page(as_user, users):
    html = as_user("admin").get(f"/people/{users['viewer'].id}").text
    assert f"panel for urn:lattice:people.person:{users['viewer'].id}" in html


def test_events_are_delivered_after_commit_and_never_on_rollback(as_user):
    c = as_user("editor")
    assert post_json(c, "/people/shout", {}).status_code == 200
    assert [e.type for e in RECEIVED] == ["people.shouted"]
    event = RECEIVED[0]
    assert event.source.startswith("/lattice/") and event.source.endswith("/people")
    assert event.to_dict()["specversion"] == "1.0" and event.subject.endswith(":1")
    RECEIVED.clear()
    assert post_json(c, "/people/shout?fail=true", {}).status_code == 400
    assert RECEIVED == []


def test_a_failing_subscriber_does_not_stop_the_others(client, db):
    events.SUBSCRIBERS["people.shouted"].insert(0, ("notes", explode))
    db.publish("people.shouted")
    assert len(RECEIVED) == 1


def test_publishing_an_undeclared_type_fails(client, db):
    with pytest.raises(ValueError, match="not declared"):
        db.publish("people.whispered")


@pytest.mark.parametrize("app, message", [
    (AppManifest(key="a", label="A", publishes=["b.x"]), "event type 'b.x' must start with 'a.'"),
    (AppManifest(key="a", label="A", references=[ReferenceKind("b.x", "X", resolve_user)]),
     "reference kind 'b.x' must start with 'a.'"),
    (AppManifest(key="a", label="A", subscribes={"a.typo": record}), "does not publish"),
    (AppManifest(key="a", label="A", panels=[RecordPanel("a.p", "P", "a/p.html", kinds=["a.nope"])]),
     "names reference kinds"),
])
def test_contract_rules_stop_the_host(app, message):
    with pytest.raises(AppError, match=message):
        create_app(apps=[app])


def test_naming_an_app_the_host_does_not_run_is_fine():
    create_app(apps=[AppManifest(key="a", label="A", subscribes={"elsewhere.done": record},
                                 panels=[RecordPanel("a.p", "P", "a/p.html",
                                                     kinds=["elsewhere.thing"])])])
