"""Events between apps: CloudEvents 1.0 on an in-process bus, and feeds that read other
systems' outboxes (ADR 0011).

    db.publish("comments.added", subject="urn:lattice:showcase.item:42", data={"id": 7})

    APP = AppManifest(key="comments", publishes=["comments.added"], …)
    APP = AppManifest(key="showcase", subscribes={"comments.added": on_comment}, …)

    def on_comment(db: Db, event: CloudEvent) -> None: …

Published events wait on the publishing transaction and are delivered after it commits;
a rolled-back request delivers nothing. Each subscriber runs in its own transaction: one
that fails is logged and undoes only its own work. Delivery is in the publishing process,
right after the commit, and is not retried: an event that must not be lost goes through
an outbox, read here by an EventFeed.

Guide: lattice/help/developer/building-apps/working-across-apps.md.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from lattice.kernel.config import settings
from lattice.kernel.database import Db, transaction
from lattice.kernel.queries import SQL
from lattice.kernel.sql import Query

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloudEvent:
    """A CloudEvents 1.0 event, as subscribers receive it."""

    type: str                       # "{app}.{event}": "comments.added"
    source: str                     # "/lattice/{host}/{app}", or the feed's source
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""               # the URN of the record it is about
    time: datetime = field(default_factory=lambda: datetime.now(UTC))
    data: dict = field(default_factory=dict)   # small: references and a few fields
    specversion: str = "1.0"
    datacontenttype: str = "application/json"

    def to_dict(self) -> dict:
        """The structured JSON form of the CloudEvents HTTP binding."""
        out = {"specversion": self.specversion, "id": self.id, "source": self.source,
               "type": self.type, "time": self.time.isoformat(),
               "datacontenttype": self.datacontenttype, "data": self.data}
        return {**out, "subject": self.subject} if self.subject else out


Subscriber = Callable[[Db, CloudEvent], None]

PUBLISHED: dict[str, str] = {}                     # event type -> publishing app
SUBSCRIBERS: dict[str, list[tuple[str, Subscriber]]] = {}   # event type -> (app, handler)
FEEDS: dict[str, EventFeed] = {}


@dataclass(frozen=True)
class EventFeed:
    """Another system's outbox, read into the bus: a named query returning CloudEvent
    columns (id, type, source, subject, time, data) for rows with `id > :after`, in id
    order, at most `:limit`. The host polls it and keeps its cursor in lattice.event_feed.
    """

    key: str                        # "{app}.{name}"
    query: Query
    every_seconds: float = 5
    batch: int = 500


def reset() -> None:
    PUBLISHED.clear()
    SUBSCRIBERS.clear()
    FEEDS.clear()


def host_name() -> str:
    return re.sub(r"[^a-z0-9]+", "-", settings.app_name.lower()).strip("-") or "lattice"


def publish(db: Db, type: str, subject: str = "", data: dict | None = None) -> CloudEvent:
    app = PUBLISHED.get(type)
    if app is None:
        raise ValueError(f"Event type {type!r} is not declared in any app's `publishes`")
    event = CloudEvent(type=type, source=f"/lattice/{host_name()}/{app}", subject=subject,
                       data=data or {})
    if db.conn.connection.driver_connection.autocommit:
        deliver(event)                       # no transaction to wait for (the tests' Db)
    else:
        db.after_commit.append(lambda: deliver(event))
    return event


def deliver(event: CloudEvent) -> None:
    """Hand one event to each subscriber, each in its own transaction."""
    for app, handler in SUBSCRIBERS.get(event.type, []):
        try:
            with transaction() as db:
                handler(db, event)
        except Exception:
            log.exception("Subscriber %s of %s failed on event %s", app, event.type, event.id)


def read_feed(feed: EventFeed) -> int:
    """Deliver the feed's new events and move its cursor past them. Returns how many.

    An advisory lock lets one process read a feed at a time; the cursor moves in the same
    transaction, after delivery, so an event is delivered at least once.
    """
    with transaction() as db:
        if not db.value(SQL.events.lock_feed, key=feed.key):
            return 0
        after = db.value(SQL.events.cursor, key=feed.key) or 0
        rows = db.all(feed.query, after=after, limit=feed.batch)
        for row in rows:
            deliver(_from_row(row))
        if rows:
            db.run(SQL.events.move_cursor, key=feed.key, last_id=rows[-1]["id"])
        return len(rows)


def _from_row(row: dict[str, Any]) -> CloudEvent:
    time = row["time"]
    if time.tzinfo is None:
        time = time.replace(tzinfo=UTC)
    return CloudEvent(type=row["type"], source=row["source"], id=str(row["id"]),
                      subject=row.get("subject") or "", time=time, data=row.get("data") or {})


async def run_feeds() -> None:
    """Started by the host when any app declares a feed: read each feed on its interval."""
    due = {key: 0.0 for key in FEEDS}
    loop = asyncio.get_running_loop()
    while True:
        now = loop.time()
        for key, feed in FEEDS.items():
            if now >= due[key]:
                due[key] = now + feed.every_seconds
                try:
                    await asyncio.to_thread(read_feed, feed)
                except Exception:
                    log.exception("Reading event feed %s failed", key)
        await asyncio.sleep(max(0.5, min(due.values()) - loop.time()))
