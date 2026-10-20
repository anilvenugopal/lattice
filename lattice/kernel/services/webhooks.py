"""Webhooks (ADR 0016, phase 3): events posted to addresses administrators register.

Every delivered event (kernel/events.py) is queued for the active webhooks that take its
type, as the exact body to post: the CloudEvent's JSON (format "cloudevents"), or a short
{"text": …} message that Slack and Teams incoming webhooks accept (format "chat"). The
background sender posts it with two headers a receiver checks:

    X-Lattice-Timestamp: 1760950000
    X-Lattice-Signature: sha256=<hex HMAC-SHA256 of "{timestamp}.{body}" with the secret>

A 2xx answer delivers it; anything else is retried up to five times, waiting longer each
time. Nothing is posted inside the request that caused the event.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from urllib.parse import urlsplit

import httpx

from lattice.kernel.config import settings
from lattice.kernel.database import Db
from lattice.kernel.queries import SQL

log = logging.getLogger(__name__)
FORMATS = [("cloudevents", "CloudEvents JSON (other systems)"), ("chat", "Chat message (Slack, Teams)")]
TIMEOUT_SECONDS = 10


def check_url(url: str) -> str:
    """An address webhooks may post to: https, or http to this machine in development."""
    parts = urlsplit(url.strip())
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if parts.scheme == "https" and parts.hostname:
        return url.strip()
    if parts.scheme == "http" and local and not settings.is_production:
        return url.strip()
    raise ValueError("A webhook address must start with https:// "
                     "(http://localhost is allowed in development)")


def new_secret() -> str:
    return secrets.token_hex(24)


def sign(secret: str, timestamp: str, body: str) -> str:
    digest = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _chat_text(event) -> str:
    from lattice.kernel.services.notifications import KINDS

    class Data(dict):
        def __missing__(self, key):
            return ""
    kind = next((k for k in KINDS.values() if k.event == event.type), None)
    title = kind.title.format_map(Data(event.data)) if kind and kind.title else event.type
    body = kind.body.format_map(Data(event.data)) if kind and kind.body else ""
    return f"[{settings.app_name}] {title}" + (f": {body}" if body else "")


def body_for(event, format: str) -> str:
    if format == "chat":
        return json.dumps({"text": _chat_text(event)})
    return json.dumps(event.to_dict(), default=str)


def queue(db: Db, event) -> int:
    """Queue the event for every active webhook that takes its type; returns how many."""
    hooks = db.all(SQL.webhooks.listening, event_type=event.type)
    for hook in hooks:
        db.run(SQL.webhooks.queue, webhook_id=hook["id"], event_id=event.id,
               event_type=event.type, subject=event.subject, body=body_for(event, hook["format"]))
    return len(hooks)


def send_due(db: Db, client: httpx.Client | None = None) -> int:
    """Post the queued deliveries that are due, in the caller's transaction (rows another
    sender holds are skipped). Returns how many were delivered."""
    delivered = 0
    with client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False) as http:
        for d in db.all(SQL.webhooks.due):
            timestamp = str(int(time.time()))
            kind = "application/cloudevents+json" if d["format"] == "cloudevents" else "application/json"
            headers = {"Content-Type": kind, "User-Agent": "Lattice webhooks",
                       "X-Lattice-Timestamp": timestamp,
                       "X-Lattice-Signature": sign(d["secret"], timestamp, d["body"])}
            try:
                res = http.post(d["url"], content=d["body"].encode(), headers=headers)
            except httpx.HTTPError as exc:
                db.run(SQL.webhooks.failed, id=d["id"], response_status=None, error=str(exc)[:500])
                continue
            if 200 <= res.status_code < 300:
                db.run(SQL.webhooks.delivered, id=d["id"], response_status=res.status_code)
                delivered += 1
            else:
                db.run(SQL.webhooks.failed, id=d["id"], response_status=res.status_code,
                       error=res.text[:500])
    return delivered
