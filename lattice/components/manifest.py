"""AppManifest: what an app adds to a host (ADR 0003). lattice/host.py reads it."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy.orm import Session

from lattice.components.grid import GridSpec
from lattice.components.search.providers import SearchProvider
from lattice.components.tiles import HomeTile
from lattice.kernel.nav import NavNode


@dataclass(frozen=True)
class AppManifest:
    """What an app adds to a host. Listed once per app package."""

    key: str                                   # URL prefix /{key}, grid key prefix {key}.
    label: str
    icon: str = ""                             # icon registry name, e.g. "demo:app"
    help_url: str = ""                         # listed in the shell's Help menu
    nav: list[NavNode] = field(default_factory=list)
    routers: list[APIRouter] = field(default_factory=list)
    grids: list[GridSpec] = field(default_factory=list)
    search: list[SearchProvider] = field(default_factory=list)
    tiles: list[HomeTile] = field(default_factory=list)
    # Folder holding templates/{key}/…; searched before core templates.
    templates: Path | None = None
    # Folder served at /static/{key}/, and stylesheets in it loaded on every page.
    # Each stylesheet declares @layer components and scopes every selector to
    # [data-app="{key}"] (ADR 0010).
    static: Path | None = None
    stylesheets: list[str] = field(default_factory=list)
    # Icons the app adds, used as icon("{key}:name"). Values are SVG path markup.
    icons: dict[str, str] = field(default_factory=dict)
    # Slot name -> template in the app's own folder ("{key}/…").
    slots: dict[str, str] = field(default_factory=dict)
    # Started with the host, cancelled at shutdown.
    background: Callable[[], Awaitable[None]] | None = None
    # Development data for `lattice seed`; receives a session and commits.
    seed: Callable[[Session], None] | None = None

    @property
    def prefix(self) -> str:
        return f"/{self.key}"
