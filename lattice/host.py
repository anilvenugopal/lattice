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
from lattice.components.manifest import AppManifest
from lattice.components.search import providers as search_providers
from lattice.components.search import router as search_router
from lattice.kernel import nav
from lattice.kernel.auth import routes as auth_routes
from lattice.kernel.auth.middleware import AuthMiddleware, is_htmx
from lattice.kernel.config import settings
from lattice.kernel.web import render
from lattice.platform import account, admin, home

APP_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
# Paths the kernel and components own; no app may use them as its key.
RESERVED_KEYS = {"home", "admin", "account", "auth", "static", "health", "docs"}


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


def _register(app: AppManifest) -> None:
    nav.add(app.nav, app.key)
    for grid in app.grids:
        grid_router.register(grid)
    for tile in app.tiles:
        tiles.register_tile(tile)
    for provider in app.search:
        search_providers.register_provider(provider)


def _reset_registries() -> None:
    nav.reset()
    grid_router.REGISTRY.clear()
    tiles.TILES.clear()
    search_providers.reset()


def create_app(apps: list[AppManifest]) -> FastAPI:
    """Build the web application for a host from its list of app manifests."""
    _reset_registries()
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
        _register(app)

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
    web.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    web.add_middleware(AuthMiddleware)
    for router in (auth_routes.router, grid_router.router, search_router.router):
        web.include_router(router)
    for app, mount in ordered:
        for router in app.routers:
            web.include_router(router, prefix=mount)
    _add_error_handlers(web)
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
