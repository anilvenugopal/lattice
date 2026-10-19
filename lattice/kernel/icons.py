"""Inline SVG icons (Lucide-style strokes, 24px grid). Use `{{ icon("name") }}` in templates.

Lookup order (ADR 0010): `icon("search")` uses the host's replacement if it has one,
then the core set below. `icon("showcase:chart")` uses the icons the `showcase` app declares.
Icons draw with `currentColor`, so they follow the light and dark themes.
Unknown names render an empty box.
"""

from __future__ import annotations

from markupsafe import Markup

PATHS: dict[str, str] = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9v12h14V9"/><path d="M10 21v-6h4v6"/>',
    "queue": '<rect x="3" y="4" width="18" height="4" rx="1"/><rect x="3" y="10" width="18" height="4" rx="1"/><rect x="3" y="16" width="18" height="4" rx="1"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "inbox": '<path d="M3 13h5l2 3h4l2-3h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.5c2.5.5 4 2.5 4 5.5"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>',
    "star": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/>',
    "check": '<path d="m5 12 5 5 9-10"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    "columns": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>',
    "download": '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8"/><path d="M4 3v5h5"/><path d="M4 13a8 8 0 0 0 14.5 4.5L20 16"/><path d="M20 21v-5h-5"/>',
    "more": '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "arrow-up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "arrow-down": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "archive": '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v11h14V9M10 13h4"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "mail-open": '<path d="M3 10 12 4l9 6v10H3z"/><path d="m3 10 9 6 9-6"/>',
    "paperclip": '<path d="m20 11-8.5 8.5a5 5 0 0 1-7-7L13 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L14 7"/>',
    "play": '<path d="M7 4v16l13-8z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1"/>',
    "retry": '<path d="M4 12a8 8 0 1 0 2.5-5.8L4 8.5"/><path d="M4 3.5v5h5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "key": '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.3-9.3M17 6l3 3M14.5 8.5l2 2"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "alert": '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
    "layout": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/>',
    "keyboard": '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "panel-right": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/>',
    "assign": '<circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-6 7-6 1.5 0 3 .3 4 1"/><path d="M16 19h6M19 16v6"/>',
    "flag": '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
    "bookmark": '<path d="M6 3h12v18l-6-4-6 4z"/>',
}


_HOST: dict[str, str] = {}
_APPS: dict[str, dict[str, str]] = {}


def reset() -> None:
    _HOST.clear()
    _APPS.clear()


def set_host_icons(icons: dict[str, str]) -> None:
    """A host may replace core icons; it may not add new unprefixed names."""
    unknown = sorted(set(icons) - set(PATHS))
    if unknown:
        raise ValueError(f"Host icons {unknown} replace no core icon")
    _HOST.update(icons)


def add_app_icons(app_key: str, icons: dict[str, str]) -> None:
    bad = sorted(name for name in icons if ":" in name)
    if bad:
        raise ValueError(f"App {app_key!r} icon names {bad} must not contain ':'")
    _APPS[app_key] = dict(icons)


def _body(name: str | None) -> str:
    name = name or ""
    if ":" in name:
        app_key, _, short = name.partition(":")
        return _APPS.get(app_key, {}).get(short, "")
    return _HOST.get(name) or PATHS.get(name, "")


def icon(name: str | None, size: int = 16, cls: str = "") -> Markup:
    body = _body(name)
    return Markup(
        f'<svg class="icon {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{body}</svg>'
    )
