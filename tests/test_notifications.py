"""Notifications (ADR 0016): notify, collapse, follow, events, clearing, the inbox and the bell."""

from pathlib import Path

import pytest
from fastapi import APIRouter, Depends

from lattice.api import (
    AppManifest,
    Db,
    NotificationKind,
    ReferenceKind,
    Resolved,
    get_db,
    notifications,
    sql_queries,
    urn,
)
from lattice.host import AppError, create_app
from lattice.testing import csrf, post_json

CHECK = sql_queries(Path(__file__).parent / "sql").checks
TICKET = urn("desk.ticket", 7)


def resolve_ticket(db, user, ticket_id):
    return Resolved(f"Ticket {ticket_id}", f"/desk/{ticket_id}") if ticket_id == "7" else None


router = APIRouter()


@router.post("/reply")
def reply(db: Db = Depends(get_db)):
    db.publish("desk.replied", subject=TICKET, data={"author": "Ann", "author_id": 1, "excerpt": "Done"})


@router.post("/close")
def close(db: Db = Depends(get_db)):
    db.publish("desk.closed", subject=TICKET)


KINDS = [NotificationKind("desk.assigned", "A ticket is yours"),
         NotificationKind("desk.urgent", "An urgent ticket", email="email"),
         NotificationKind("desk.daily", "Ticket news", email="digest"),
         NotificationKind("desk.reply", "A reply on a ticket you follow", event="desk.replied",
                          title="{author} replied", body="{excerpt}", clears=["desk.closed"])]


@pytest.fixture
def host_apps():
    return [AppManifest(key="desk", label="Desk", routers=[router], notifications=KINDS,
                        publishes=["desk.replied", "desk.closed"],
                        references=[ReferenceKind("desk.ticket", "Ticket", resolve_ticket)])]


def inbox(db, user):
    return db.all(CHECK.notifications_of, user_id=user.id)


def test_notify_collapses_unread_ones_about_one_record_and_skips_the_actor(client, db, users):
    ed, viewer = users["editor"], users["viewer"]
    notifications.notify(db, [ed.id, viewer.id], "desk.assigned", "Ticket 7 is yours",
                         subject=TICKET, actor_id=viewer.id)
    notifications.notify(db, [ed.id], "desk.assigned", "Ticket 7 is still yours", subject=TICKET)
    [one] = inbox(db, ed)
    assert (one["count"], one["title"]) == (2, "Ticket 7 is still yours")
    assert inbox(db, viewer) == []                              # the actor is not told
    with pytest.raises(ValueError, match="not declared"):
        notifications.notify(db, [ed.id], "desk.nope", "x")


def test_followers_hear_of_an_event_and_its_closing_clears_it(client, as_user, users, db):
    ed = users["editor"]
    notifications.follow(db, [ed.id, users["admin"].id], TICKET)    # admin (id 1) is the author
    c = as_user("viewer")
    c.post("/desk/reply", headers={"X-CSRF-Token": csrf(c)})
    [note] = inbox(db, ed)
    assert (note["title"], note["body"], note["subject"]) == ("Ann replied", "Done", TICKET)
    assert inbox(db, users["admin"]) == []
    c.post("/desk/close", headers={"X-CSRF-Token": csrf(c)})
    assert inbox(db, ed)[0]["resolved_at"] is not None
    assert notifications.unread(db, ed.id) == 0


def test_the_inbox_is_each_users_own(as_user, users, db):
    notifications.notify(db, [users["viewer"].id], "desk.assigned", "For the viewer", subject=TICKET)
    theirs = inbox(db, users["viewer"])[0]["id"]
    c = as_user("editor")
    assert "For the viewer" not in c.get("/_grid/notifications/rows?view=all").text
    assert c.get(f"/_grid/notifications/panel/{theirs}").status_code == 404
    assert post_json(c, "/_grid/notifications/action/read", {"ids": [theirs]}).status_code == 400
    res = c.get(f"/account/notifications/{theirs}", follow_redirects=False)
    assert res.headers["location"] == "/account/notifications"     # not theirs: nothing opened
    assert inbox(db, users["viewer"])[0]["read_at"] is None


def test_open_marks_read_and_goes_to_the_record(as_user, users, db):
    notifications.notify(db, [users["viewer"].id], "desk.assigned", "Yours", subject=TICKET)
    c = as_user("viewer")
    assert 'class="bell__count"' in c.get("/account/notifications/badge").text
    assert ">1<" in c.get("/account/notifications/badge").text
    note = inbox(db, users["viewer"])[0]
    res = c.get(f"/account/notifications/{note['id']}", follow_redirects=False)
    assert res.status_code == 303 and res.headers["location"] == "/desk/7"
    assert inbox(db, users["viewer"])[0]["read_at"] is not None
    assert " hidden" in c.get("/account/notifications/badge").text


def test_mark_all_read_and_dismiss(as_user, users, db):
    for i in range(2):
        notifications.notify(db, [users["viewer"].id], "desk.assigned", f"N{i}", subject=f"{TICKET}{i}")
    c = as_user("viewer")
    post_json(c, "/_grid/notifications/action/read_all", {"ids": []})
    assert notifications.unread(db, users["viewer"].id) == 0
    ids = [n["id"] for n in inbox(db, users["viewer"])]
    post_json(c, "/_grid/notifications/action/dismiss", {"ids": ids})
    assert inbox(db, users["viewer"]) == []


def test_follow_toggles_on_a_record_the_user_may_see(as_user, users, db):
    c = as_user("viewer")
    res = c.post("/account/follow", data={"subject": TICKET}, headers={"X-CSRF-Token": csrf(c)})
    assert res.status_code == 200 and "Following" in res.text
    assert notifications.following(db, users["viewer"].id, TICKET)
    c.post("/account/follow", data={"subject": TICKET}, headers={"X-CSRF-Token": csrf(c)})
    assert not notifications.following(db, users["viewer"].id, TICKET)
    gone = urn("desk.ticket", 8)
    assert c.post("/account/follow", data={"subject": gone},
                  headers={"X-CSRF-Token": csrf(c)}).status_code == 404


def test_old_notifications_are_deleted(client, db, users):
    notifications.notify(db, [users["viewer"].id], "desk.assigned", "Old")
    db.run(CHECK.age_notifications, days=91)
    notifications.expire(db)
    assert inbox(db, users["viewer"]) == []


@pytest.mark.parametrize("manifest, message", [
    (AppManifest(key="desk", label="D", notifications=[NotificationKind("other.x", "X")]),
     "must start with 'desk.'"),
    (AppManifest(key="desk", label="D", notifications=[NotificationKind("desk.x", "X", event="desk.nope")]),
     "names event 'desk.nope'"),
])
def test_kinds_are_checked(manifest, message):
    with pytest.raises(AppError, match=message):
        create_app(apps=[manifest])


# ── Email (phase 2) ──────────────────────────────────────────────────────────

def emails(db, user):
    return db.all(CHECK.emails_to, user_id=user.id)


def test_a_kind_that_emails_queues_one_and_a_choice_overrides_it(client, db, users):
    ed, viewer = users["editor"], users["viewer"]
    notifications.choose(db, viewer.id, "desk.urgent", "app")
    notifications.notify(db, [ed.id, viewer.id], "desk.urgent", "Server down", body="secret detail",
                         subject=TICKET)
    notifications.notify(db, [ed.id], "desk.urgent", "Server still down", subject=TICKET)
    [one] = emails(db, ed)                                     # the second waits on the first
    assert one["subject"] == "Server down" and "/account/notifications/" in one["body"]
    assert "secret detail" not in one["body"]                 # titles and links, never content
    assert emails(db, viewer) == []
    notifications.notify(db, [ed.id], "desk.assigned", "Ticket 9", subject=urn("desk.ticket", 9))
    assert len(emails(db, ed)) == 1                            # in-app kinds send nothing


def test_without_a_mail_server_emails_are_logged(client, db, users):
    notifications.notify(db, [users["editor"].id], "desk.urgent", "Down", subject=TICKET)
    assert notifications.send_due(db) == 0
    [email] = emails(db, users["editor"])
    assert email["status"] == "logged"
    assert inbox(db, users["editor"])[0]["id"] in email["notification_ids"]


def test_failed_sends_are_retried_then_given_up(client, db, users, monkeypatch):
    from lattice.kernel.services import mail

    def refuse(*args):
        raise OSError("connection refused")
    monkeypatch.setattr(mail, "send", refuse)
    notifications.notify(db, [users["editor"].id], "desk.urgent", "Down", subject=TICKET)
    notifications.send_due(db)
    [email] = emails(db, users["editor"])
    assert (email["status"], email["attempts"], email["last_error"]) == ("queued", 1, "connection refused")
    assert notifications.send_due(db) == 0                     # not due again yet

    sent = []
    monkeypatch.setattr(mail, "send", lambda to, subject, body: sent.append(to))
    notifications.notify(db, [users["viewer"].id], "desk.urgent", "Down", subject=TICKET)
    assert notifications.send_due(db) == 1 and sent == ["viewer@test.io"]


def test_a_daily_summary_lists_unread_ones_once_a_day(client, db, users):
    from datetime import UTC, datetime
    ed = users["editor"]
    notifications.notify(db, [ed.id], "desk.daily", "Ticket 7 changed", subject=TICKET)
    notifications.notify(db, [ed.id], "desk.daily", "Ticket 8 changed", subject=urn("desk.ticket", 8))
    assert notifications.queue_digests(db, datetime(2026, 10, 20, 3, tzinfo=UTC)) == 0   # too early
    assert notifications.queue_digests(db, datetime(2026, 10, 20, 9, tzinfo=UTC)) == 1
    [digest] = emails(db, ed)
    assert digest["kind"] == "digest" and "Ticket 7 changed" in digest["body"]
    assert "Ticket 8 changed" in digest["body"] and len(digest["notification_ids"]) == 2
    assert notifications.queue_digests(db, datetime(2026, 10, 20, 9, tzinfo=UTC)) == 0   # once a day


def test_people_choose_how_they_are_told(as_user, users, db):
    c = as_user("viewer")
    page = c.get("/account/notifications/settings").text
    assert "An urgent ticket" in page and 'name="kind:desk.urgent"' in page
    res = c.post("/account/notifications/settings", headers={"X-CSRF-Token": csrf(c)},
                 data={"kind:desk.urgent": "digest", "kind:desk.nope": "email", "kind:desk.daily": "fax"})
    assert res.status_code == 200
    chosen = notifications.choices(db, users["viewer"].id)
    assert (chosen["desk.urgent"], chosen["desk.daily"]) == ("digest", "digest")    # fax ignored


def test_administrators_read_sent_email_and_send_a_test(as_user, users, db):
    assert as_user("editor").get("/admin/email").status_code == 403
    c = as_user("admin")
    assert "No mail server is set" in c.get("/admin/email").text
    res = post_json(c, "/_grid/emails/action/test", {"ids": []}).json()
    assert "Test email queued to admin@test.io" in res["message"]
    assert emails(db, users["admin"])[0]["kind"] == "test"
