"""Template rendering. Routes call `render_page()` for full pages and `render()` for partials."""

from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import Request, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer
from jinja2 import FileSystemLoader
from markupsafe import Markup, escape

from lattice.kernel.auth.cookies import set_cookie
from lattice.kernel.auth.sessions import AUTH_METHOD_LABELS
from lattice.kernel.config import settings
from lattice.kernel.display import initials
from lattice.kernel.icons import icon
from lattice.kernel.nav import nav_context
from lattice.kernel.services import preferences
from lattice.kernel.slots import render_slot

CORE_TEMPLATES = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=CORE_TEMPLATES)
env = templates.env
# tojson writes ids into pages; a UUID id (Taskline's views) is written as its text.
env.policies["json.dumps_kwargs"] = {"sort_keys": True, "default": str}


def set_host_assets(template_dirs: list[Path], stylesheets: list[str],
                    help_links: list[tuple[str, str, str]]) -> None:
    """Called by create_app.

    template_dirs: searched in order before core (host, then apps).
    stylesheets: URLs loaded after the core app.css (app stylesheets, then the host theme).
    help_links: (label, url, icon) for the Help menu.
    """
    env.loader = FileSystemLoader([*template_dirs, CORE_TEMPLATES])
    env.globals.update(extra_stylesheets=stylesheets, help_links=help_links)


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds") + "Z"
    return value.isoformat() if isinstance(value, date) else str(value)


def time_tag(value, mode: str = "auto") -> Markup:
    """<time> element that app.js formats in the browser's time zone.

    mode: "auto" follows the user's time_format preference, or "relative",
    "datetime", "date".
    """
    if not value:
        return Markup('<span class="muted">—</span>')
    if isinstance(value, date) and not isinstance(value, datetime):
        # A calendar day has no time of day: shown as stored, never moved by a time zone.
        return Markup(f'<time datetime="{value.isoformat()}" data-fmt="day">{value.isoformat()}</time>')
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    fallback = value.strftime("%Y-%m-%d") if mode == "date" else value.strftime("%Y-%m-%d %H:%M")
    return Markup(f'<time datetime="{_iso(value)}" data-fmt="{mode}">{fallback} UTC</time>')


class _Row(dict):
    def __missing__(self, key):
        return ""


def fmt(template: str, row: dict) -> str:
    """Format display text such as "{ref} · {title}" with a row dict. Missing keys render empty."""
    return template.format_map(_Row(row))


def fmt_url(template: str, row: dict) -> str:
    """Format a link such as "/work/{id}" with a row dict, URL-encoding each inserted value."""
    return template.format_map(_Row({k: quote(str(v), safe="") for k, v in row.items()
                                     if v is not None}))


def label_for(col, value):
    """Display text for a value of a grid Column, using its `labels`."""
    return col.labels.get(str(value), value) if col and col.labels else value


def tone_for(col, value) -> str:
    """Badge tone for a value of a grid Column, using its `tones`."""
    return col.tones.get(str(value), "neutral") if col else "neutral"


def number(value, digits: int = 0) -> str:
    if value is None or value == "":
        return "—"
    return f"{value:,.{digits}f}"


def money(value) -> str:
    return "—" if value is None else f"${value:,.0f}"


def csrf_field(request: Request) -> Markup:
    token = escape(request.state.csrf_token)
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')


# The request being handled, for template helpers that need it inside macros imported
# without context (e.g. `ref()` in a grid cell). Set by AuthMiddleware for every request.
CURRENT_REQUEST: ContextVar[Request | None] = ContextVar("lattice_request", default=None)


env.globals.update(
    settings=settings,
    icon=icon,
    time_tag=time_tag,
    fmt=fmt,
    slot=render_slot,
    extra_stylesheets=[],
    help_links=[],
    fmt_url=fmt_url,
    label_for=label_for,
    initials=initials,
    auth_method_labels=AUTH_METHOD_LABELS,
    tone_for=tone_for,
    prefs=preferences,
    pick=lambda row, keys: {k: row.get(k) for k in keys},
)
env.filters.update(number=number, money=money)


def js(value) -> Markup:
    """A value as a JavaScript literal inside a double-quoted HTML attribute (Alpine expressions).

    Use `@click="run({{ key|js }})"`, never `'{{ key }}'`: the browser decodes HTML entities
    before Alpine evaluates the attribute, so plain autoescaping does not protect it.
    """
    return Markup(escape(json.dumps(value, default=str)))


env.filters["js"] = js


FLASH_COOKIE = "flash"
_flash_signer = URLSafeTimedSerializer(settings.secret_key, salt="flash")


def flash(response: Response, request: Request, message: str, tone: str = "success") -> None:
    """Show `message` as a toast on the next full page load (use with a redirect after a form post)."""
    set_cookie(response, request, FLASH_COOKIE, _flash_signer.dumps([message, tone]), max_age=60)


def _take_flash(request: Request) -> dict | None:
    try:
        message, tone = _flash_signer.loads(request.cookies.get(FLASH_COOKIE, ""), max_age=60)
    except (BadSignature, ValueError):
        return None
    return {"message": message, "tone": tone}


def render(request: Request, template: str, *, status_code: int = 200,
           headers: dict | None = None, **ctx):
    """Render a template; context goes in as keyword arguments, as for render_page()."""
    # Only full page loads show toasts from a flash; HTMX partials leave it in place.
    take = FLASH_COOKIE in request.cookies and request.headers.get("HX-Request") != "true"
    pending = _take_flash(request) if take else None
    ctx = {"current_user": getattr(request.state, "user", None),
           "csrf_field": lambda: csrf_field(request), "flash": pending, **ctx}
    response = templates.TemplateResponse(request, template, ctx, status_code=status_code,
                                          headers=headers)
    if take:
        response.delete_cookie(FLASH_COOKIE)
    return response


def render_page(request: Request, template: str, nav_key: str, *, status_code: int = 200,
                **ctx):
    """Render a page inside the shell. `nav_key` is a NavNode key from lattice/kernel/nav/manifest.py.

    Set `crumb` to append a record name to the breadcrumb (detail pages).
    """
    return render(request, template, status_code=status_code,
                  nav=nav_context(request.state.user, nav_key), **ctx)


def toast(message: str, tone: str = "success", **events) -> dict:
    """Response headers that show a toast (and fire extra HTMX events) on the client."""
    return {"HX-Trigger": json.dumps({"toast": {"message": message, "tone": tone}, **events})}
