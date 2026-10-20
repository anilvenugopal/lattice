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

from lattice.components import forms, references, tiles
from lattice.components import record as record_component
from lattice.components.chart import router as chart_router
from lattice.components.forms import render as form_router
from lattice.components.grid import router as grid_router
from lattice.components.grid.engine import GridTimeout
from lattice.components.help import content as help_content
from lattice.components.help import provider as help_provider
from lattice.components.help import router as help_router
from lattice.components.help import search as help_search
from lattice.components.manifest import AppManifest
from lattice.components.map import router as map_router
from lattice.components.search import providers as search_providers
from lattice.components.search import router as search_router
from lattice.components.timeline import router as timeline_router
from lattice.kernel import css_rules, events, icons, nav, slots
from lattice.kernel.auth import permissions
from lattice.kernel.auth import routes as auth_routes
from lattice.kernel.auth.middleware import AuthMiddleware, is_htmx
from lattice.kernel.config import settings
from lattice.kernel.database import NotFound
from lattice.kernel.services import files, notifications
from lattice.kernel.web import render, set_host_assets
from lattice.platform import account, admin, attachments, home

APP_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
ACCENT_TONES = ("", "info", "success", "warning", "danger", "accent", "neutral")
# Paths the kernel and components own; no app may use them as its key.
RESERVED_KEYS = {"home", "admin", "account", "auth", "static", "health", "docs", "host",
                 "help", "lattice"}
# Lattice's own help (user guide and developer documentation), registered as "lattice".
CORE_HELP = Path(__file__).parent / "help"
# Core pages a host may replace by placing a template of the same name in its templates/.
HOST_OVERRIDABLE = {"auth/login.html", "base/error.html", "pages/home.html",
                    "email/notification.txt", "email/digest.txt", "email/test.txt"}


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
    for spec in app.maps:
        if not spec.key.startswith(app.key + "."):
            fail(f"map key {spec.key!r} must start with {app.key + '.'!r}")
        try:
            spec.check()
        except ValueError as exc:
            fail(str(exc))
    if app.accent not in ACCENT_TONES:
        fail(f"accent {app.accent!r} must be one of {', '.join(t for t in ACCENT_TONES if t)}")
    for spec in app.timelines:
        if not spec.key.startswith(app.key + "."):
            fail(f"timeline key {spec.key!r} must start with {app.key + '.'!r}")
        try:
            spec.check()
        except ValueError as exc:
            fail(str(exc))
    for spec in app.forms:
        if not spec.key.startswith(app.key + "."):
            fail(f"form key {spec.key!r} must start with {app.key + '.'!r}")
    for kind in app.notifications:
        if not kind.key.startswith(app.key + "."):
            fail(f"notification kind {kind.key!r} must start with {app.key + '.'!r}")
    for name, items in (("reference kind", [k.key for k in app.references]),
                        ("record panel", [p.key for p in app.panels]),
                        ("event type", app.publishes)):
        for key in items:
            if not key.startswith(app.key + "."):
                fail(f"{name} {key!r} must start with {app.key + '.'!r}")
    for kind in app.documents:
        if not kind.key.startswith(app.key + "."):
            fail(f"document kind {kind.key!r} must start with {app.key + '.'!r}")
    for schema in app.schemas:
        if not schema.id.startswith(app.key + "."):
            fail(f"schema id {schema.id!r} must start with {app.key + '.'!r}")
    for chart in app.charts:
        if not chart.key.startswith(app.key + "."):
            fail(f"chart key {chart.key!r} must start with {app.key + '.'!r}")
        try:
            chart.check()
        except ValueError as exc:
            fail(str(exc))
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
        for path in [*templates.rglob("*.html"), *templates.rglob("*.txt")]:
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
    try:
        permissions.register(app.permissions, "lattice." if platform else f"{app.key}.")
    except permissions.BadPermission as exc:
        raise AppError(f"App {app.key!r}: {exc}") from exc
    nav.add(app.nav, "" if platform else app.key)
    icons.add_app_icons(app.key, app.icons)
    if app.accent:
        nav.ACCENTS[app.key] = app.accent
    for slot_name, template in app.slots.items():
        slots.add(slot_name, template)
    for grid in app.grids:
        grid_router.register(grid)
    for chart in app.charts:
        chart_router.register(chart)
    for spec in app.maps:
        map_router.register(spec)
    for spec in app.timelines:
        timeline_router.register(spec)
    for kind in app.notifications:
        notifications.register(kind)
    for spec in app.forms:
        forms.register_form(spec)
    for schema in app.schemas:
        forms.register_schema(schema)
    for kind in app.documents:
        forms.register_schema(kind.schema_def())
        forms.register_form(kind.form)
    for kind in app.references:
        references.register(kind)
    record_component.PANELS.extend(app.panels)
    for event_type in app.publishes:
        events.PUBLISHED[event_type] = app.key
    for event_type, handler in app.subscribes.items():
        events.SUBSCRIBERS.setdefault(event_type, []).append((app.key, handler))
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


def _check_contracts(app_keys: set[str]) -> None:
    """Catch typos between apps: a subscription or panel that names another app in this host
    must name an event type or reference kind that app declares. Naming an app the host
    doesn't run is fine: that subscription or panel simply never applies."""
    for event_type, handlers in events.SUBSCRIBERS.items():
        if event_type.split(".")[0] in app_keys and event_type not in events.PUBLISHED:
            apps = ", ".join(sorted({app for app, _ in handlers}))
            raise AppError(f"App {apps!r} subscribes to {event_type!r}, which its app does "
                           "not publish")
    for kind in notifications.KINDS.values():
        for event_type in [kind.event, *kind.clears]:
            if event_type and event_type.split(".")[0] in app_keys and event_type not in events.PUBLISHED:
                raise AppError(f"Notification kind {kind.key!r} names event {event_type!r}, "
                               "which its app does not publish")
    for panel in record_component.PANELS:
        if panel.kinds != "*":
            unknown = [k for k in panel.kinds
                       if k.split(".")[0] in app_keys and k not in references.KINDS]
            if unknown:
                raise AppError(f"Record panel {panel.key!r} names reference kinds no app "
                               f"declares: {', '.join(unknown)}")


def _check_permissions() -> None:
    """Every permission a page, grid, action, Ctrl+J source or help topic names is declared."""
    named = [(f"nav node {n.key!r}", n.permission) for n in nav.NODES]
    for spec in grid_router.REGISTRY.values():
        named.append((f"grid {spec.key!r}", spec.permission))
        named += [(f"action {spec.key}.{a.key}", a.permission) for a in spec.actions]
    named += [(f"chart {c.key!r}", c.permission) for c in chart_router.REGISTRY.values()]
    named += [(f"form {f.key!r}", f.permission) for f in forms.FORMS.values()]
    named += [(f"map {m.key!r}", m.permission) for m in map_router.REGISTRY.values()]
    named += [(f"timeline {t.key!r}", t.permission) for t in timeline_router.REGISTRY.values()]
    named += [(f"record panel {p.key!r}", p.permission) for p in record_component.PANELS]
    named += [(f"Ctrl+J source {p.key!r}", p.permission) for p in search_providers.registered()]
    named += [(f"help topic {t.url}", t.permission)
              for app in help_content.HELP.values() for t in app.topics.values()]
    for where, permission in named:
        if permission and permission not in permissions.CATALOGUE:
            raise AppError(f"{where} names permission {permission!r}, which no app declares")


def _reset_registries() -> None:
    permissions.reset()
    nav.reset()
    help_content.reset()
    icons.reset()
    slots.reset()
    grid_router.REGISTRY.clear()
    chart_router.REGISTRY.clear()
    map_router.REGISTRY.clear()
    timeline_router.REGISTRY.clear()
    notifications.reset()
    forms.FORMS.clear()
    forms.SCHEMAS.clear()
    references.KINDS.clear()
    record_component.PANELS.clear()
    events.reset()
    tiles.TILES.clear()
    search_providers.reset()


def create_app(apps: list[AppManifest], host_dir: Path | None = None,
               icons_override: dict[str, str] | None = None,
               slot_templates: dict[str, str] | None = None,
               folder_stores: dict[str, str | Path] | None = None) -> FastAPI:
    """Build the web application for a host from its list of app manifests.

    host_dir: the host's folder. Optional `templates/` replaces the core pages in
    HOST_OVERRIDABLE and holds slot templates under `host/`; optional `static/` is
    served at /static/host/, and its `theme.css` (brand tokens only) loads after core CSS.
    icons_override: replacements for core icons, by name.
    slot_templates: slot name -> template under host/ in the host's templates.
    folder_stores: label -> path of mounted shares the folder picker browses, added to
    LATTICE_FOLDER_STORES (ADR 0017).
    """
    _reset_registries()
    try:
        files.register_folder_stores({**settings.folder_stores, **(folder_stores or {})})
    except ValueError as exc:
        raise AppError(str(exc)) from exc
    if host_dir:
        _check_host(host_dir)
    platform_first, platform_last = [home.APP], [attachments.APP, admin.APP, account.APP]
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
    _check_permissions()
    _check_contracts({a.key for a, _ in ordered})
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
    for router in (auth_routes.router, grid_router.router, chart_router.router,
                   map_router.router, timeline_router.router, form_router.router, search_router.router,
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

    @web.exception_handler(GridTimeout)
    async def grid_timeout(request: Request, exc: GridTimeout):
        if _wants_json(request) or is_htmx(request):
            return JSONResponse({"detail": exc.message}, status_code=503)
        return _error_response(request, 503, exc.message)

    @web.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound):
        return _error_response(request, 404, "Not found.")

    @web.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return _error_response(request, 422,
                               "The address or form contains a value that is not valid.")
