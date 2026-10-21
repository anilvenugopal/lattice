"""Attachments (ADR 0017): files kept with any record, by its URN.

The platform app (lattice/platform/attachments.py) draws the panel and serves the routes;
apps use these functions, for example to remove a deleted record's files:

    attachments.remove_all(db, urn("showcase.claim", 42))

Access is the caller's to check: a user may reach a record's attachments only if the
record's reference resolves for them.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Iterable
from pathlib import PurePath

from lattice.kernel.config import settings
from lattice.kernel.database import Db
from lattice.kernel.queries import SQL
from lattice.kernel.services import files

# Shown in the browser; every other type is only ever downloaded.
INLINE = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}


class Refused(ValueError):
    """An upload the site does not accept: its type, or its size."""


def allowed_types() -> set[str]:
    return {t.strip().lower().lstrip(".") for t in settings.attachment_types.split(",") if t.strip()}


def clean_name(name: str) -> str:
    """The file's own name, without any folders the browser sent; at most 255 characters."""
    base = PurePath(name.replace("\\", "/")).name.strip().replace("\x00", "")
    return (base or "file")[-255:]


def add(db: Db, user_id: int, subject: str, name: str, chunks: Iterable[bytes]) -> dict:
    """Store a file and record it; returns {id, name, size, content_type}. Raises Refused."""
    name = clean_name(name)
    extension = PurePath(name).suffix.lower().lstrip(".")
    if extension not in allowed_types():
        raise Refused(f"{name}: files of type .{extension or '?'} are not accepted here")
    key = files.new_key()
    limit = settings.attachment_max_mb * 1024 * 1024

    def counted():                      # Lattice's own limit, whatever the store does
        seen = 0
        for chunk in chunks:
            seen += len(chunk)
            if seen > limit:
                raise files.TooLarge
            yield chunk
    try:
        size, digest = files.attachments_store().put(key, counted(), max_bytes=limit)
    except files.TooLarge:
        raise Refused(f"{name} is larger than {settings.attachment_max_mb} MB") from None
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    attachment_id = db.value(SQL.attachments.add, subject=subject, name=name,
                             content_type=content_type, size=size, sha256=digest, store_key=key,
                             added_by=user_id)
    return {"id": attachment_id, "name": name, "size": size, "content_type": content_type}


def on_subject(db: Db, subject: str) -> list[dict]:
    return db.all(SQL.attachments.on_subject, subject=subject)


def get(db: Db, attachment_id: int) -> dict | None:
    return db.first(SQL.attachments.by_id, id=attachment_id)


def remove(db: Db, attachment_id: int) -> None:
    """Forget one attachment and delete its file once the transaction commits."""
    key = db.value(SQL.attachments.remove, id=attachment_id)
    if key:
        _delete_after_commit(db, [key])


def remove_all(db: Db, subject: str) -> int:
    """Forget every attachment of a record (when the owning app deletes the record)."""
    keys = [r["store_key"] for r in db.all(SQL.attachments.remove_all, subject=subject)]
    _delete_after_commit(db, keys)
    return len(keys)


def _delete_after_commit(db: Db, keys: list[str]) -> None:
    def delete() -> None:
        for key in keys:
            files.attachments_store().delete(key)
    if db.conn.connection.driver_connection.autocommit:
        delete()
    else:
        db.after_commit.append(delete)
