"""References to records in any app, as URNs (ADR 0011): urn:lattice:{kind}:{id}.

An app that owns records declares each kind with a resolver:

    def resolve_item(db, user, item_id) -> Resolved | None: …   # None: gone, or not for this user
    APP = AppManifest(key="showcase", references=[ReferenceKind("showcase.item", "Item", resolve_item)])

Any template draws a reference with `{{ ref(urn) }}`: the record's title linked to its page,
with a status badge, or "Unavailable" when the record is gone or the user may not see it.
Apps store and pass references as text and never import the owning app.

Guide: lattice/help/developer/building-apps/working-across-apps.md.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from markupsafe import Markup

from lattice.kernel.database import Db, transaction
from lattice.kernel.web import CURRENT_REQUEST, env

PREFIX = "urn:lattice:"
_URN = re.compile(r"^urn:lattice:([a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*):(.+)$")


class BadReference(ValueError):
    """Not a Lattice URN."""


@dataclass(frozen=True)
class Ref:
    """A parsed reference."""

    kind: str                       # "showcase.item"
    id: str                         # the owning app's id, as text

    @property
    def urn(self) -> str:
        return f"{PREFIX}{self.kind}:{self.id}"

    @property
    def app(self) -> str:
        return self.kind.partition(".")[0]


def urn(kind: str, record_id: Any) -> str:
    """The reference to one record: urn("showcase.item", 42) -> "urn:lattice:showcase.item:42"."""
    return Ref(kind, str(record_id)).urn


def parse(value: str) -> Ref:
    m = _URN.match(value or "")
    if not m:
        raise BadReference(f"Not a Lattice reference: {value!r}")
    return Ref(m.group(1), m.group(2))


@dataclass(frozen=True)
class Resolved:
    """What a reference shows: its title, link and, optionally, a status badge."""

    title: str
    url: str = ""
    subtitle: str = ""
    badge: str = ""
    tone: str = "neutral"


Resolver = Callable[[Db, Any, str], "Resolved | None"]


@dataclass(frozen=True)
class ReferenceKind:
    key: str                        # "{app}.{kind}"
    label: str                      # "Item": shown beside unresolvable references
    resolve: Resolver               # (db, user, id) -> Resolved, or None when not visible
    icon: str = ""


KINDS: dict[str, ReferenceKind] = {}


def register(kind: ReferenceKind) -> None:
    if kind.key in KINDS and KINDS[kind.key] is not kind:
        raise ValueError(f"Reference kind {kind.key!r} is declared twice")
    KINDS[kind.key] = kind


def resolve(db: Db, user, value: str) -> Resolved | None:
    """The reference as this user may see it; None for an unknown kind, a missing record, or
    one the user may not see."""
    try:
        ref = parse(value)
    except BadReference:
        return None
    kind = KINDS.get(ref.kind)
    return kind.resolve(db, user, ref.id) if kind else None


def render_ref(db: Db, user, value: str) -> Markup:
    """HTML for one reference: a link with its badge, or a muted "Unavailable"."""
    found = resolve(db, user, value)
    if found is None:
        try:
            label = KINDS[parse(value).kind].label
        except (BadReference, KeyError):
            label = "Record"
        return Markup('<span class="ref ref--missing">{} unavailable</span>').format(label)
    title = (Markup('<a class="ref__title" href="{}">{}</a>').format(found.url, found.title)
             if found.url else Markup('<span class="ref__title">{}</span>').format(found.title))
    badge = (Markup(' <span class="badge tone-{}">{}</span>').format(found.tone, found.badge)
             if found.badge else "")
    sub = Markup(' <span class="ref__sub">{}</span>').format(found.subtitle) if found.subtitle else ""
    return Markup('<span class="ref">{}{}{}</span>').format(title, badge, sub)


def _ref_global(value: str) -> Markup:
    request = CURRENT_REQUEST.get()
    db = getattr(request.state, "db", None)
    if db is not None:
        return render_ref(db, request.state.user, value)
    with transaction() as own:                 # a page rendered without the request's Db
        return render_ref(own, request.state.user, value)


env.globals["ref"] = _ref_global
