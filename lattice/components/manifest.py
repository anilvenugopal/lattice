"""AppManifest: what an app adds to a host (ADR 0003). lattice/host.py reads it."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter

from lattice.components.chart import ChartSpec
from lattice.components.documents import DocumentKind
from lattice.components.forms import FormSpec, SchemaDef
from lattice.components.grid import GridSpec
from lattice.components.map import MapSpec
from lattice.components.record import RecordPanel
from lattice.components.references import ReferenceKind
from lattice.components.search.providers import SearchProvider
from lattice.components.tiles import HomeTile
from lattice.components.timeline import TimelineSpec
from lattice.kernel.auth.permissions import Permission
from lattice.kernel.database import Db
from lattice.kernel.events import Subscriber
from lattice.kernel.migrate import Library
from lattice.kernel.nav import NavNode
from lattice.kernel.services.notifications import NotificationKind


@dataclass(frozen=True)
class AppManifest:
    """What an app adds to a host. Listed once per app package."""

    key: str                                   # URL prefix /{key}, grid key prefix {key}.
    label: str                      # app name in menus, Help and Ctrl+J
    icon: str = ""                             # icon registry name, e.g. "showcase:app"
    help_url: str = ""                         # listed in the shell's Help menu
    nav: list[NavNode] = field(default_factory=list)  # the app's pages; every page has a node
    # FastAPI routers, mounted as declared (paths start with /{key})
    routers: list[APIRouter] = field(default_factory=list)
    # registered for actions, export, Ctrl+J and tiles
    grids: list[GridSpec] = field(default_factory=list)
    charts: list[ChartSpec] = field(default_factory=list)  # served at /_chart/{key}/data
    maps: list[MapSpec] = field(default_factory=list)      # served at /_map/{key}/data
    timelines: list[TimelineSpec] = field(default_factory=list)  # /_timeline/{key}/data
    forms: list[FormSpec] = field(default_factory=list)  # JSON Schema forms: /_form/{key}/render
    schemas: list[SchemaDef] = field(default_factory=list)  # named schemas forms can apply
    documents: list[DocumentKind] = field(default_factory=list)  # kinds in the document store
    # Working with other apps (ADR 0011): kinds of record others may reference, panels on
    # other apps' record pages, and events this app announces and receives.
    references: list[ReferenceKind] = field(default_factory=list)
    panels: list[RecordPanel] = field(default_factory=list)
    publishes: list[str] = field(default_factory=list)      # event types: "{key}.{event}"
    subscribes: dict[str, Subscriber] = field(default_factory=dict)  # event type -> handler
    # What people may be told about (ADR 0016): kinds for notify(), or tied to an event.
    notifications: list[NotificationKind] = field(default_factory=list)
    search: list[SearchProvider] = field(default_factory=list)  # extra Ctrl+J sources
    tiles: list[HomeTile] = field(default_factory=list)  # count tiles on the home page
    # Folder holding templates/{key}/…; searched before core templates.
    templates: Path | None = None
    # Folder served at /static/{key}/, and stylesheets in it loaded on every page.
    # Each stylesheet declares @layer components and scopes every selector to
    # [data-app="{key}"] (ADR 0010).
    static: Path | None = None
    stylesheets: list[str] = field(default_factory=list)  # file names inside `static`
    # The app's accent (ADR 0010): a tone, never a colour, marking its rail entry and page
    # headers so it stays recognisable inside the host's one theme.
    accent: Literal["", "info", "success", "warning", "danger", "accent", "neutral"] = ""
    # Icons the app adds, used as icon("{key}:name"). Values are SVG path markup.
    icons: dict[str, str] = field(default_factory=dict)
    # What the app's users may do: checked with require(), permission=, can().
    permissions: list[Permission] = field(default_factory=list)
    # Schemas of libraries the app uses, as (schema, migrations folder), e.g. geoengine.SCHEMA.
    # `lattice migrate` applies them before the app's own, once even if several apps list them.
    library_schemas: list[tuple[str, Path]] = field(default_factory=list)
    # Libraries that migrate themselves (a callable, not a folder), e.g. Taskline.
    libraries: list[Library] = field(default_factory=list)
    # Folder of the app's SQL: named queries in *.sql, migrations in schema/*.sql.
    # The migrations create and fill the Postgres schema named after the app's key.
    sql: Path | None = None
    # Folder of Markdown help topics with index.md and an optional help.toml page map.
    help: Path | None = None
    # Slot name -> template in the app's own folder ("{key}/…").
    slots: dict[str, str] = field(default_factory=dict)
    # Started with the host, cancelled at shutdown.
    background: Callable[[], Awaitable[None]] | None = None
    # Development data for `lattice seed`; receives a Db in the seed's transaction.
    seed: Callable[[Db], None] | None = None

    @property
    def prefix(self) -> str:
        return f"/{self.key}"
