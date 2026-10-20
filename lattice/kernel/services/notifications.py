"""Notifications (ADR 0016): each person's inbox, fed by apps and by following records.

    notifications.notify(db, [owner_id], "incidents.assigned", "INC-42 is yours",
                         subject=urn("incidents.incident", 42), actor_id=user.id)
    notifications.follow(db, user_id, urn("showcase.claim", 7))

A NotificationKind an app declares can name an event: when it is published, the people
following the event's subject are told (all but the actor), and its `clears` events
resolve open notifications of that kind about the record. Notifications refer to records
by URN and are drawn at read time, so the reader's access applies then.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from lattice.kernel.config import settings
from lattice.kernel.database import Db
from lattice.kernel.queries import SQL
from lattice.kernel.services import mail

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationKind:
    """What people may be told about, declared by an app (AppManifest.notifications)."""

    key: str                        # "{app}.{name}": "comments.on_followed"
    label: str                      # for people: "New comment on a record you follow"
    description: str = ""
    # When this event is published, tell the people following its subject.
    event: str = ""
    title: str = ""                 # formatted with the event's data: "{author} commented"
    body: str = ""                  # likewise: "{excerpt}"
    # Events that resolve open notifications of this kind about the same record.
    clears: tuple[str, ...] | list[str] = field(default_factory=tuple)
    # How people are told unless they choose otherwise: in the app only, by email right
    # away, or in a daily email summary (Account › Notification settings).
    email: Literal["app", "email", "digest"] = "app"


CHANNELS = [("app", "In the app only"), ("email", "Email right away"),
            ("digest", "Daily email summary")]

KINDS: dict[str, NotificationKind] = {}


def register(kind: NotificationKind) -> None:
    KINDS[kind.key] = kind


def reset() -> None:
    KINDS.clear()


def notify(db: Db, user_ids: Iterable[int], kind: str, title: str, body: str = "",
           subject: str = "", actor_id: int | None = None) -> None:
    """Tell these people, in the caller's transaction. An unread notification of the same
    kind about the same record is updated, with its count raised, instead of repeated."""
    if kind not in KINDS:
        raise ValueError(f"Notification kind {kind!r} is not declared in any app's `notifications`")
    ids = sorted({int(u) for u in user_ids if u is not None and u != actor_id})
    if not ids:
        return
    values = {"kind": kind, "title": title[:255], "body": body[:2000], "subject": subject,
              "actor_id": actor_id}
    folded = db.all(SQL.notifications.collapse, user_ids=ids, **values)
    fresh = [u for u in ids if u not in {r["user_id"] for r in folded}]
    added = db.all(SQL.notifications.add, user_ids=fresh, **values) if fresh else []
    db.run(SQL.notifications.queue_emails, ids=[r["id"] for r in [*folded, *added]],
           base=settings.public_url.rstrip("/"), label=KINDS[kind].label,
           default_channel=KINDS[kind].email)


def resolve(db: Db, subject: str, kinds: Iterable[str]) -> None:
    """Clear open notifications of these kinds about a record (it was resolved, closed…)."""
    db.run(SQL.notifications.resolve, subject=subject, kinds=list(kinds))


def follow(db: Db, user_ids: int | Iterable[int], subject: str) -> None:
    ids = [user_ids] if isinstance(user_ids, int) else list(user_ids)
    if ids:
        db.run(SQL.notifications.follow_many, user_ids=ids, subject=subject)


def unfollow(db: Db, user_id: int, subject: str) -> None:
    db.run(SQL.notifications.unfollow, user_id=user_id, subject=subject)


def following(db: Db, user_id: int, subject: str) -> bool:
    return bool(db.value(SQL.notifications.following, user_id=user_id, subject=subject))


def unread(db: Db, user_id: int) -> int:
    return db.value(SQL.notifications.unread, user_id=user_id) or 0


def choices(db: Db, user_id: int) -> dict[str, str]:
    """Each declared kind's channel for this person: their choice, else the kind's default."""
    chosen = {r["kind"]: r["channel"] for r in db.all(SQL.notifications.choices, user_id=user_id)}
    return {key: chosen.get(key, kind.email) for key, kind in KINDS.items()}


def choose(db: Db, user_id: int, kind: str, channel: str) -> None:
    if kind not in KINDS or channel not in dict(CHANNELS):
        raise ValueError(f"Unknown kind {kind!r} or channel {channel!r}")
    db.run(SQL.notifications.choose, user_id=user_id, kind=kind, channel=channel)


def queue_digests(db: Db, now: datetime | None = None) -> int:
    """Queue each person's daily summary, once the digest hour has passed and none went out in
    the last 20 hours. Returns how many were queued."""
    now = now or datetime.now(UTC)
    if now.hour < settings.notification_digest_hour:
        return 0
    rows = db.all(SQL.notifications.digest_due,
                  digest_kinds=[k for k, kind in KINDS.items() if kind.email == "digest"])
    base = settings.public_url.rstrip("/")
    people: dict[int, list[dict]] = {}
    for r in rows:
        people.setdefault(r["user_id"], []).append(r)
    for user_id, items in people.items():
        lines = [f"- {r['title']}" + (f" ({r['count']} times)" if r["count"] > 1 else "")
                 for r in items[:25]]
        more = [f"…and {len(items) - 25} more."] if len(items) > 25 else []
        body = "\n".join([f"You have {len(items)} unread notification(s):", "", *lines, *more, "",
                          f"Read them: {base}/account/notifications", "",
                          f"Choose how you are told: {base}/account/notifications/settings"])
        db.run(SQL.notifications.queue_digest, user_id=user_id, to_address=items[0]["email"],
               subject=f"{len(items)} unread notification(s)", body=body,
               ids=[r["id"] for r in items])
    return len(people)


def send_due(db: Db) -> int:
    """Send the queued emails that are due, in the caller's transaction (rows other senders
    hold are skipped). With no mail server they are kept as logged. Returns how many went."""
    sent = 0
    for email in db.all(SQL.notifications.due_emails):
        try:
            mail.send(email["to_address"], email["subject"], email["body"])
            db.run(SQL.notifications.email_done, id=email["id"], status="sent")
            sent += 1
        except mail.NotConfigured:
            db.run(SQL.notifications.email_done, id=email["id"], status="logged")
        except Exception as exc:
            log.warning("Email %s to %s failed: %s", email["id"], email["to_address"], exc)
            db.run(SQL.notifications.email_failed, id=email["id"], error=str(exc)[:500])
    return sent


def expire(db: Db) -> None:
    db.run(SQL.notifications.expire, days=settings.notification_days)


class _Data(dict):
    def __missing__(self, key):
        return ""


def on_event(db: Db, event) -> None:
    """Called for every delivered event: tell followers, and clear what it closes."""
    if not event.subject:
        return
    for kind in KINDS.values():
        if event.type in kind.clears:
            resolve(db, event.subject, [kind.key])
        if kind.event == event.type:
            data = _Data(event.data)
            followers = [r["user_id"] for r in db.all(SQL.notifications.followers,
                                                      subject=event.subject)]
            notify(db, followers, kind.key, kind.title.format_map(data) or kind.label,
                   kind.body.format_map(data), subject=event.subject,
                   actor_id=event.data.get("actor_id") or event.data.get("author_id"))
