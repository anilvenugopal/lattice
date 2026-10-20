"""File stores (ADR 0017): where attachment files live, and the mounted shares people browse.

    store = files.attachments_store()          # LATTICE_FILES_DIR
    size, digest = store.put("2026/10/ab12…", chunks, max_bytes=25 * 2**20)
    with store.open("2026/10/ab12…") as f: …

    files.FOLDER_STORES["claims-share"].list("2026/CLM-26-004871")

Only a local or mounted folder is built; S3 and SharePoint stores will implement the same
methods. A path is always relative to the store's root, and one that leaves it is refused.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from lattice.kernel.config import settings


class TooLarge(Exception):
    """A file passed the size limit while it was being written."""


class BadPath(ValueError):
    """A path outside the store's root, or one that does not exist."""


@dataclass(frozen=True)
class Folder:
    name: str
    path: str                       # relative to the store's root, "/"-separated


class LocalStore:
    """Files in a folder on this machine, or on a share mounted on it."""

    def __init__(self, root: Path | str, label: str = ""):
        self.root = Path(root).resolve()
        self.label = label or self.root.name

    def _path(self, relative: str) -> Path:
        target = (self.root / relative.strip("/")).resolve()
        if target != self.root and not target.is_relative_to(self.root):
            raise BadPath(f"{relative!r} is outside the store")
        return target

    def put(self, key: str, chunks: Iterable[bytes], max_bytes: int) -> tuple[int, str]:
        """Write a file from chunks; returns its size and SHA-256. Nothing is left behind if
        it passes max_bytes."""
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        size, digest = 0, hashlib.sha256()
        try:
            with partial.open("wb") as out:
                for chunk in chunks:
                    size += len(chunk)
                    if size > max_bytes:
                        raise TooLarge
                    digest.update(chunk)
                    out.write(chunk)
            partial.replace(target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        return size, digest.hexdigest()

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list(self, path: str = "") -> list[Folder]:
        """The folders directly inside `path`, by name; hidden ones are left out."""
        here = self._path(path)
        if not here.is_dir():
            raise BadPath(f"{path!r} is not a folder")
        base = here.relative_to(self.root).as_posix()
        return sorted((Folder(e.name, e.name if base == "." else f"{base}/{e.name}")
                       for e in os.scandir(here) if e.is_dir() and not e.name.startswith(".")),
                      key=lambda f: f.name.lower())

    def make_folder(self, path: str, name: str) -> Folder:
        if not re.fullmatch(r"[^/\\\x00-\x1f]{1,120}", name.strip()) or name.strip() in (".", ".."):
            raise BadPath(f"{name!r} is not a folder name")
        target = self._path(f"{path}/{name.strip()}")
        target.mkdir(exist_ok=True)
        return Folder(target.name, target.relative_to(self.root).as_posix())

    def exists(self, path: str) -> bool:
        try:
            return self._path(path).is_dir()
        except BadPath:
            return False


_ATTACHMENTS: LocalStore | None = None
# Mounted shares people may browse with the folder picker, by key.
FOLDER_STORES: dict[str, LocalStore] = {}


def attachments_store() -> LocalStore:
    global _ATTACHMENTS
    if _ATTACHMENTS is None or _ATTACHMENTS.root != Path(settings.files_dir).resolve():
        _ATTACHMENTS = LocalStore(settings.files_dir, "Attachments")
    return _ATTACHMENTS


def new_key() -> str:
    """A random name to store an uploaded file under, grouped by month."""
    from datetime import UTC, datetime
    return f"{datetime.now(UTC):%Y/%m}/{uuid.uuid4().hex}"


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "share"


def split(value: str) -> tuple[LocalStore, str]:
    """A folder picker value, "{store}:{path}", as its store and path. Raises BadPath."""
    key, _, path = (value or "").partition(":")
    store = FOLDER_STORES.get(key)
    if store is None:
        raise BadPath(f"No folder store {key!r}")
    store._path(path)                                       # refuses a path outside it
    return store, path.strip("/")


def check_folder(value: str) -> str:
    """A folder picker value that names an existing folder, normalised; raises BadPath."""
    store, path = split(value)
    if not store.exists(path):
        raise BadPath(f"{path or '/'} is not a folder in {store.label}")
    return f"{slug(store.label)}:{path}"


def folder_label(value: str) -> str:
    """How a folder picker value reads: "Claims share / 2026 / CLM-26-004871"."""
    try:
        store, path = split(value)
    except BadPath:
        return value
    return " / ".join([store.label, *[p for p in path.split("/") if p]])


def register_folder_stores(stores: dict[str, str | Path]) -> None:
    """Label -> path, from LATTICE_FOLDER_STORES and create_app(folder_stores=…)."""
    FOLDER_STORES.clear()
    for label, path in stores.items():
        if not Path(path).is_dir():
            raise ValueError(f"Folder store {label!r}: {path} is not a folder")
        FOLDER_STORES[slug(label)] = LocalStore(path, label)
