"""Hosts: create_app and the app checks (ADR 0003).

A host is `create_app(apps=[...])`. Each app is a package that exposes one
AppManifest (lattice/components/manifest.py). create_app registers Lattice's own platform apps (home, admin,
account) and the host's apps with the kernel and component registries, mounts
their routes, and checks that every app stays inside its own namespace.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from lattice.components import tiles
from lattice.components.grid import router as grid_router
from lattice.components.help import content as help_content
from lattice.components.help import provider as help_provider
from lattice.components.help import router as help_router
from lattice.components.help import search as help_search
from lattice.components.manifest import AppManifest
from lattice.components.search import providers as search_providers
from lattice.components.search import router as search_router
from lattice.kernel import css_rules, icons, nav, slots
from lattice.kernel.auth import routes as auth_routes
from lattice.kernel.auth.middleware import AuthMiddleware, is_htmx
from lattice.kernel.config import settings
from lattice.kernel.web import render, set_host_assets
from lattice.platform import account, admin, home

APP_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
# Paths the kernel and components own; no app may use them as its key.
RESERVED_KEYS = {"home", "admin", "account", "auth", "static", "health", "docs", "host",
                 "help", "lattice"}
# Lattice's own help (user guide and developer documentation), registered as "lattice".
CORE_HELP = Path(__file__).parent / "help"
# Core pages a host may replace by placing a template of the same name in its templates/.
HOST_OVERRIDABLE = {"auth/login.html", "base/error.html", "pages/home.html"}


class AppError(Exception):
    """An app manifest breaks a rule. The message names the app and the rule."""


def _check(app: AppManifest) -> None:
    def fail(rule: str):
        raise AppError(f"App {app.key!r}: {rule}")

    if not APP_KEY.match(app.key):
        fail("key must be lowercase letters, digits and underscores, starting with a letter")
    if app.key in RESERVED_KEYS:
        fail(f"key is reserved by Lattice ({', '.join(sorted(RESERVED_KEYS))})")
    for node in app.nav:
        path = node.route.split("?")[0]
        if path != app.prefix and not path.startswith(app.prefix + "/"):
            fail(f"nav node {node.key!r} route {node.route!r} must start with {app.prefix}")
    for grid in app.grids:
        if not grid.key.startswith(app.key + "."):
            fail(f"grid key {grid.key!r} must start with {app.key + '.'!r}")
        if not grid.path.startswith(app.prefix + "/") and grid.path != app.prefix:
            fail(f"grid {grid.key!r} path {grid.path!r} must start with {app.prefix}")
    if app.templates and app.templates.is_dir():
        extra = sorted(p.name for p in app.templates.iterdir() if p.name != app.key)
        if extra:
            fail(f"templates folder may only contain {app.key}/ (found {extra})")
    for slot_name, template in app.slots.items():
        if not template.startswith(app.key + "/"):
            fail(f"slot {slot_name!r} template {template!r} must be in {app.key}/")
    if app.stylesheets and not app.static:
        fail("declares stylesheets but no static folder")
    for name in app.stylesheets:
        path = app.static / name
        if not path.is_file():
            fail(f"stylesheet {name!r} not found in {app.static}")
        errors = css_rules.app_stylesheet_errors(path.read_text(), app.key)
        if errors:
            fail(f"stylesheet {name!r}: " + "; ".join(errors))


def _check_host(host_dir: Path) -> None:
    templates = host_dir / "templates"
    if templates.is_dir():
        for path in templates.rglob("*.html"):
            name = path.relative_to(templates).as_posix()
            if name not in HOST_OVERRIDABLE and not name.startswith("host/"):
                raise AppError(f"Host template {name!r}: a host may override only "
                               f"{', '.join(sorted(HOST_OVERRIDABLE))}, or add templates under host/")
    theme = host_dir / "static" / "theme.css"
    if theme.is_file():
        errors = css_rules.host_theme_errors(theme.read_text())
        if errors:
            raise AppError("Host theme.css: " + "; ".join(errors))


def _register(app: AppManifest, platform: bool) -> None:
    nav.add(app.nav, "" if platform else app.key)
    icons.add_app_icons(app.key, app.icons)
    for slot_name, template in app.slots.items():
        slots.add(slot_name, template)
    for grid in app.grids:
        grid_router.register(grid)
    for tile in app.tiles:
        tiles.register_tile(tile)
    for provider in app.search:
        search_providers.register_provider(provider)


def _load_help(ordered: list[tuple[AppManifest, str]], platform: list[AppManifest]) -> None:
    """Lattice's help first (it owns the platform pages), then each app's help folder."""
    sources = [("lattice", "Lattice", CORE_HELP, "")]
    sources += [(a.key, a.label, a.help, a.key) for a, _ in ordered
                if a.help and a not in platform]
    for key, label, root, nav_app in sources:
        owned = {n.key for n in nav.NODES if n.app == nav_app}
        try:
            help_content.register(help_content.load_help(key, label, root, owned))
        except help_content.HelpError as exc:
            raise AppError(str(exc)) from exc
    help_search.build([t for app in help_content.HELP.values() for t in app.topics.values()])
    search_providers.register_provider(help_provider.PROVIDER)


def _reset_registries() -> None:
    nav.reset()
    help_content.reset()
    icons.reset()
    slots.reset()
    grid_router.REGISTRY.clear()
    tiles.TILES.clear()
    search_providers.reset()


def create_app(apps: list[AppManifest], host_dir: Path | None = None,
               icons_override: dict[str, str] | None = None,
               slot_templates: dict[str, str] | None = None) -> FastAPI:
    """Build the web application for a host from its list of app manifests.

    host_dir: the host's folder. Optional `templates/` replaces the core pages in
    HOST_OVERRIDABLE and holds slot templates under `host/`; optional `static/` is
    served at /static/host/, and its `theme.css` (brand tokens only) loads after core CSS.
    icons_override: replacements for core icons, by name.
    slot_templates: slot name -> template under host/ in the host's templates.
    """
    _reset_registries()
    if host_dir:
        _check_host(host_dir)
    platform_first, platform_last = [home.APP], [admin.APP, account.APP]
    keys = [a.key for a in apps]
    duplicates = {k for k in keys if keys.count(k) > 1}
    if duplicates:
        raise AppError(f"App keys used more than once: {', '.join(sorted(duplicates))}")
    for app in apps:
        _check(app)

    # Registration order is rail order: Home, the host's apps, Administration, Account.
    ordered = [(a, "") for a in platform_first] + [(a, a.prefix) for a in apps] + \
              [(a, a.prefix) for a in platform_last]
    for app, _mount in ordered:
        _register(app, platform=app in platform_first + platform_last)
    _load_help(ordered, platform_first + platform_last)
    icons.set_host_icons(icons_override or {})
    for slot_name, template in (slot_templates or {}).items():
        slots.add(slot_name, template)

    host_static = host_dir / "static" if host_dir and (host_dir / "static").is_dir() else None
    stylesheets = [f"/static/{a.key}/{name}" for a, _ in ordered for name in a.stylesheets]
    if host_static and (host_static / "theme.css").is_file():
        stylesheets.append("/static/host/theme.css")
    template_dirs = [host_dir / "templates"] if host_dir and (host_dir / "templates").is_dir() else []
    template_dirs += [a.templates for a, _ in ordered if a.templates]
    set_host_assets(template_dirs, stylesheets,
                    [(a.label, a.help_url, a.icon) for a, _ in ordered if a.help_url])

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        tasks = [asyncio.create_task(a.background()) for a, _ in ordered if a.background]
        yield
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    web = FastAPI(title=settings.app_name, lifespan=lifespan,
                  docs_url=None if settings.is_production else "/docs", redoc_url=None)
    # More specific static mounts first: /static would otherwise catch /static/{key}/.
    for app, _ in ordered:
        if app.static:
            web.mount(f"/static/{app.key}", StaticFiles(directory=app.static))
    if host_static:
        web.mount("/static/host", StaticFiles(directory=host_static))
    web.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    web.add_middleware(AuthMiddleware)
    for router in (auth_routes.router, grid_router.router, search_router.router,
                   help_router.router):
        web.include_router(router)
    for app, mount in ordered:
        for router in app.routers:
            web.include_router(router, prefix=mount)
    _add_error_handlers(web)
    web.state.apps = apps          # the host's own apps, for `lattice seed`
    return web


def _wants_json(request: Request) -> bool:
    return (request.url.path.startswith("/_grid/") and request.method != "GET") or \
        "application/json" in request.headers.get("accept", "")


def _error_response(request: Request, status_code: int, detail: str, headers=None):
    """JSON for API and HTMX callers; the error page for browser page loads."""
    if _wants_json(request) or (is_htmx(request) and status_code < 500):
        return JSONResponse({"detail": detail}, status_code=status_code, headers=headers)
    titles = {403: "Access denied", 404: "Page not found", 422: "Invalid request"}
    return render(request, "base/error.html", status_code=status_code, code=status_code,
                  title=titles.get(status_code, "Something went wrong"),
                  detail=detail if status_code != 404 else "The page you asked for does not exist.")


def _add_error_handlers(web: FastAPI) -> None:
    @web.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return _error_response(request, exc.status_code, exc.detail, getattr(exc, "headers", None))

    @web.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return _error_response(request, 422,
                               "The address or form contains a value that is not valid.")
