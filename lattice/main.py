"""FastAPI application.

Server-rendered: Jinja2 templates, HTMX for partial updates, Alpine.js for
client state inside a component. Route handlers are sync `def` unless they read
the request body.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from lattice.components.grid import router as grid_router
from lattice.components.search import router as search_router
from lattice.features import inbox, jobs, work_items
from lattice.kernel.auth import routes as auth
from lattice.kernel.auth.middleware import AuthMiddleware, is_htmx
from lattice.kernel.config import settings
from lattice.kernel.web import render
from lattice.platform import account, admin
from lattice.platform import home as shell

# Feature modules: each provides `router`, and optionally `background()`, a coroutine
# started with the app and cancelled at shutdown.
FEATURES = (work_items, jobs, inbox)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(m.background()) for m in FEATURES if hasattr(m, "background")]
    yield
    for task in tasks:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=settings.app_name, lifespan=lifespan,
              docs_url=None if settings.is_production else "/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.add_middleware(AuthMiddleware)

for module in (shell, auth, account, admin, grid_router, search_router, *FEATURES):
    app.include_router(module.router)


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


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return _error_response(request, exc.status_code, exc.detail, getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return _error_response(request, 422, "The address or form contains a value that is not valid.")
