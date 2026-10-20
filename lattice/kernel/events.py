"""Events between apps: CloudEvents 1.0 on an in-process bus (ADR 0011).

    db.publish("comments.added", subject="urn:lattice:showcase.claim:42", data={"id": 7})

    APP = AppManifest(key="comments", publishes=["comments.added"], …)
    APP = AppManifest(key="showcase", subscribes={"comments.added": on_comment}, …)

    def on_comment(db: Db, event: CloudEvent) -> None: …

Published events wait on the publishing transaction and are delivered after it commits;
a rolled-back request delivers nothing. Each subscriber runs in its own transaction: one
that fails is logged and undoes only its own work. Delivery is in the publishing process,
right after the commit, and is not retried. A reaction that must not be missed reads
state instead (ADR 0012): Taskline's finished runs are read from its views on a timer.

Guide: lattice/help/developer/building-apps/working-across-apps.md.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lattice.kernel.config import settings
from lattice.kernel.database import Db, transaction

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


def reset() -> None:
    PUBLISHED.clear()
    SUBSCRIBERS.clear()


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
