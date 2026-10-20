"""Rules for stylesheets that hosts and apps add (ADR 0010).

create_app checks every host theme and app stylesheet with these functions and
refuses to start on a violation. tests/test_css_architecture.py applies the same
kind of rules to Lattice's own stylesheets.
"""

from __future__ import annotations

import re

# The semantic tokens a host theme may redefine: the brand set.
ALLOWED_HOST_TOKENS = re.compile(
    r"^--(brand|brand-hover|brand-alt|accent|text-on-accent|link|font-ui|font-mono"
    r"|surface-[a-z-]+|text(-[a-z0-9-]+)?)$")
COLOR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(|:\s*(?:white|black|red|blue|green|gray|grey)\b")


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(text: str) -> list[tuple[str, str]]:
    """(selector, declarations) for every style rule, looking inside @layer blocks."""
    text = strip_comments(text)
    text = re.sub(r"@layer\s+[\w-]+\s*\{", "", text)   # unwrap layer blocks
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text)]


def _tokens(body: str) -> set[str]:
    return set(re.findall(r"(--[\w-]+)\s*:", body))


def app_stylesheet_errors(text: str, app_key: str) -> list[str]:
    """An app styles only its own pages: every selector starts with [data-app="{key}"]."""
    errors = []
    scope = f'[data-app="{app_key}"]'
    clean = strip_comments(text)
    if not re.search(r"@layer\s+components\b", clean):
        errors.append("must declare @layer components")
    if COLOR_LITERAL.search(clean):
        errors.append("contains a colour literal; use a semantic token")
    if "var(--p-" in clean:
        errors.append("uses a --p-* token; use a semantic token")
    if "!important" in clean:
        errors.append("uses !important")
    for selector, _ in _rules(text):
        for part in selector.split(","):
            if not part.strip().startswith(scope):
                errors.append(f"selector {part.strip()!r} is not scoped to {scope}")
    return errors


FONT_FACE = re.compile(r"@font-face\s*\{([^{}]*)\}")
FONT_FACE_PROPERTIES = {"font-family", "src", "font-weight", "font-style", "font-display",
                        "font-stretch", "unicode-range"}


def _font_face_errors(body: str) -> list[str]:
    """A host may load its own font files, from the host folder only."""
    errors = []
    declared = set(re.findall(r"([\w-]+)\s*:", re.sub(r"url\([^)]*\)", "url()", body)))
    if extra := sorted(declared - FONT_FACE_PROPERTIES):
        errors.append(f"@font-face sets {extra}; only font descriptors are allowed")
    for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", body):
        if "://" in url or url.startswith("//") or (url.startswith("/") and not url.startswith("/static/host/")):
            errors.append(f"@font-face loads {url!r}; fonts must come from the host folder "
                          "(a relative path, or /static/host/…)")
    return errors


def host_theme_errors(text: str) -> list[str]:
    """A host theme sets only allowed brand tokens, in both :root and [data-mode="dark"], and
    may load font files from the host folder with @font-face."""
    errors = []
    clean = strip_comments(text)
    for body in FONT_FACE.findall(clean):
        errors += _font_face_errors(body)
    text = clean = FONT_FACE.sub("", clean)
    if not re.search(r"@layer\s+settings\b", clean):
        errors.append("must declare @layer settings")
    if COLOR_LITERAL.search(re.sub(r"--[\w-]+\s*:[^;]*;", "", clean)):
        errors.append("contains a colour outside a token definition")
    by_selector: dict[str, set[str]] = {}
    for selector, body in _rules(text):
        if selector not in (":root", '[data-mode="dark"]'):
            errors.append(f"selector {selector!r}: only :root and [data-mode=\"dark\"] are allowed")
            continue
        declared = set(re.findall(r"([\w-]+)\s*:", body))
        not_tokens = sorted(d for d in declared if not d.startswith("--"))
        if not_tokens:
            errors.append(f"{selector} sets properties {not_tokens}; only tokens are allowed")
        tokens = _tokens(body)
        disallowed = sorted(t for t in tokens if not ALLOWED_HOST_TOKENS.match(t))
        if disallowed:
            errors.append(f"{selector} sets tokens a host may not change: {disallowed}")
        by_selector.setdefault(selector, set()).update(tokens)
    light, dark = by_selector.get(":root", set()), by_selector.get('[data-mode="dark"]', set())
    if light != dark:
        errors.append(f"light and dark must set the same tokens; differ in {sorted(light ^ dark)}")
    return errors
