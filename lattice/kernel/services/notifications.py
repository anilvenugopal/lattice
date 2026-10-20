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

from lattice.kernel.config import settings
from lattice.kernel.database import Db
from lattice.kernel.queries import SQL

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
    folded = {r["user_id"] for r in db.all(SQL.notifications.collapse, user_ids=ids, **values)}
    fresh = [u for u in ids if u not in folded]
    if fresh:
        db.run(SQL.notifications.add, user_ids=fresh, **values)


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
