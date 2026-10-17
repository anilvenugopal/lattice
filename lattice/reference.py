"""The Reference pages of the developer documentation, generated from the code.

`lattice docs build` writes them into lattice/help/developer/reference/;
`lattice docs check` (and tests/test_reference.py) fails when a committed page
differs from what the code produces, so the Reference cannot go stale.
Descriptions come from docstrings, field comments, Settings descriptions,
argparse help and the `{# … #}` comment above each macro.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import inspect
import re
import textwrap
import typing
from pathlib import Path

import lattice.api as api
from lattice.components import grid, manifest, tiles
from lattice.components.search import providers
from lattice.kernel import config, icons, slots
from lattice.kernel.css_rules import ALLOWED_HOST_TOKENS
from lattice.kernel.nav import manifest as nav

ROOT = Path(__file__).parent
OUT = ROOT / "help" / "developer" / "reference"
MACROS = ROOT / "templates" / "components" / "macros.html"
TOKENS = ROOT / "static" / "css" / "1-settings" / "tokens.css"
TEMPLATES = ROOT / "templates"


def _page(title: str, summary: str, order: int, source: str, body: str, keywords: str = "") -> str:
    meta = f"---\ntitle: {title}\nsummary: {summary}\norder: {order}\n"
    meta += f"keywords: {keywords}\n" if keywords else ""
    note = (f"> [!NOTE]\n> Generated from `{source}` by `lattice docs build`. "
            "Change the code, not this page.\n")
    return f"{meta}---\n\n{note}\n{body.strip()}\n"


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:] + "." if text else ""


def _first_paragraph(doc: str | None) -> str:
    return inspect.cleandoc(doc or "").split("\n\n")[0].replace("\n", " ")


# ── Dataclasses ──────────────────────────────────────────────────────────────

def _fields(cls) -> list[list[str]]:
    """(name, type, default, description) for each field, the description taken from its comment."""
    lines, _ = inspect.getsourcelines(cls)
    source = textwrap.dedent("".join(lines))
    node = ast.parse(source).body[0]
    src_lines = source.splitlines()
    rows = []
    for stmt in node.body:
        if not isinstance(stmt, ast.AnnAssign):
            continue
        name = stmt.target.id
        line = src_lines[stmt.lineno - 1]
        comment = line[stmt.end_col_offset:].strip().removeprefix("#").strip()
        above, n = [], stmt.lineno - 2
        while not comment and n >= 0 and src_lines[n].strip().startswith("#"):
            above.insert(0, src_lines[n].strip().removeprefix("#").strip())
            n -= 1
        rows.append([f"`{name}`", f"`{ast.unparse(stmt.annotation)}`",
                     _default(stmt.value), comment or " ".join(above)])
    return rows


def _default(value: ast.expr | None) -> str:
    if value is None:
        return "required"
    if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "field":
        for kw in value.keywords:
            if kw.arg == "default_factory":
                return {"list": "`[]`", "dict": "`{}`"}.get(ast.unparse(kw.value), ast.unparse(kw.value))
            if kw.arg == "default":
                return f"`{ast.unparse(kw.value)}`"
    return f"`{ast.unparse(value)}`"


def _dataclass(cls, heading: str = "##") -> str:
    tree = ast.parse(textwrap.dedent(inspect.getsource(cls))).body[0]
    doc = ast.get_docstring(tree) or ""
    out = [f"{heading} {cls.__name__}", ""]
    if doc:
        out += [doc, ""]
    out.append(_table(["Field", "Type", "Default", "Description"], _fields(cls)))
    return "\n".join(out) + "\n"


# ── Pages ────────────────────────────────────────────────────────────────────

API_PAGES = {"AppManifest": "app-manifest", "NavNode": "app-manifest", "HomeTile": "app-manifest",
             "SearchProvider": "app-manifest", "SearchResult": "app-manifest", "settings": "settings"}
API_PAGES |= {name: "grid" for name in ("Action", "ActionContext", "ActionResult", "Column",
                                        "Field", "Filter", "GridSpec", "Palette", "View")}


VALUES = {"settings": "The running configuration, read from `LATTICE_*` environment variables.",
          "DEV_USERS": "(email, name, password, roles) of the development accounts `lattice seed` "
                       "creates; app tests sign in as them."}


def _api_page() -> str:
    groups: list[tuple[str, list[str]]] = []
    for line in inspect.getsource(api).split("__all__ = [", 1)[1].splitlines():
        line = line.strip()
        if line.startswith("#"):
            groups.append((line.lstrip("# "), []))
        elif line.startswith('"') and groups:
            groups[-1][1].extend(re.findall(r'"(\w+)"', line))
    body = [_first_paragraph(api.__doc__), "",
            "```python\nfrom lattice.api import AppManifest, GridSpec, render_page\n```", ""]
    for title, names in groups:
        rows = []
        for name in names:
            obj = getattr(api, name)
            kind = ("class" if inspect.isclass(obj) else "function" if callable(obj)
                    else "module" if inspect.ismodule(obj) else "value")
            doc = obj.__doc__ if kind in ("class", "function", "module") else ""
            if kind == "class" and dataclasses.is_dataclass(obj) and doc and doc.startswith(name + "("):
                doc = ""                                  # the generated dataclass signature
            if kind == "value":
                doc = VALUES.get(name) or f"`{obj!r}`"
            page = API_PAGES.get(name)
            label = f"[`{name}`]({page}.md#{name.lower()})" if page and page != "settings" else \
                f"[`{name}`]({page}.md)" if page else f"`{name}`"
            if kind == "function":
                label += " " + f"`{_signature(obj)}`"
            rows.append([label, kind, _first_paragraph(doc)])
        body += [f"## {title}", "", _table(["Name", "Kind", "Description"], rows), ""]
    return _page("Python API", "Every name in lattice.api, the only module an app imports.", 10,
                 "lattice/api.py", "\n".join(body), "import public api lattice.api")


def _signature(fn) -> str:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return "(…)"
    params = []
    for p in sig.parameters.values():
        text = p.name if p.kind is not p.VAR_POSITIONAL else f"*{p.name}"
        text = f"**{p.name}" if p.kind is p.VAR_KEYWORD else text
        if p.default is not p.empty:
            text += f"={p.default!r}"
        params.append(text)
    return f"({', '.join(params)})"


def _manifest_page() -> str:
    body = ["An app is a package that exports one `AppManifest` as `APP`. A host lists the "
            "apps it runs in `create_app(apps=[…])`, which checks every rule below before "
            "the host starts.", ""]
    for cls in (manifest.AppManifest, nav.NavNode, tiles.HomeTile,
                providers.SearchProvider, providers.SearchResult):
        body.append(_dataclass(cls))
    return _page("App manifest", "AppManifest and the records it holds: NavNode, HomeTile, "
                 "SearchProvider.", 20, "lattice/components/manifest.py`, `lattice/kernel/nav/manifest.py`, `lattice/components/tiles.py` and `lattice/components/search/providers.py",
                 "\n".join(body), "manifest navnode navigation tile provider")


def _grid_page() -> str:
    kinds = ", ".join(f"`{k}`" for k in typing.get_args(grid.spec.ColumnKind))
    tones = ", ".join(f"`{k}`" for k in typing.get_args(grid.spec.Tone))
    body = [_first_paragraph(grid.spec.__doc__), "",
            f"**Column kinds:** {kinds}.", "", f"**Tones:** {tones}.", ""]
    for cls in (grid.GridSpec, grid.Column, grid.Filter, grid.View, grid.Action, grid.Field,
                grid.ActionContext, grid.ActionResult, grid.Palette):
        body.append(_dataclass(cls))
    return _page("Grid", "GridSpec and the classes that describe columns, filters, views and "
                 "actions.", 30, "lattice/components/grid/spec.py", "\n".join(body),
                 "gridspec column action filter view table list")


def _settings_page() -> str:
    rows = []
    for name, info in config.Settings.model_fields.items():
        default = info.default
        shown = "unset" if default is None else f"`{str(default).lower() if isinstance(default, bool) else default}`"
        rows.append([f"`LATTICE_{name.upper()}`", shown, info.description or ""])
    body = [_first_paragraph(config.Settings.__doc__),
            "Values are read from the environment, then from a `.env` file in the working folder.",
            "", _table(["Variable", "Default", "Description"], rows)]
    return _page("Settings", "Every LATTICE_ environment variable, its default and what it does.",
                 40, "lattice/kernel/config.py", "\n".join(body),
                 "environment variables configuration env oidc sso")


def _cli_page(parser: argparse.ArgumentParser) -> str:
    body = [f"{parser.description} Run it with `uv run lattice …` from the repository root.", ""]
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    helps = {c.dest: c.help for c in sub._choices_actions}
    for name, cmd in sub.choices.items():
        usage = cmd.format_usage().removeprefix("usage: ").strip()
        body += [f"## {name}", "", _sentence(helps.get(name, "")), "",
                 f"```text\n{usage}\n```", ""]
        rows = []
        for a in cmd._actions:
            if isinstance(a, argparse._HelpAction):
                continue
            arg = ", ".join(a.option_strings) or a.dest
            choices = f" One of: {', '.join(a.choices)}." if a.choices else ""
            default = f" Default: `{a.default}`." if a.option_strings and a.default not in (None, False, []) else ""
            text = _sentence(a.help or "")
            rows.append([f"`{arg}`", f"{text}{choices}{default}".strip()])
        if rows:
            body += [_table(["Argument", "Description"], rows), ""]
    return _page("Command line", "The lattice command: migrations, users, seed data, the "
                 "development server and these docs.", 50, "lattice/cli.py", "\n".join(body),
                 "cli command migrate seed create-user dev docs")


_MACRO = re.compile(r"(?:\{#(?P<doc>(?:(?!#\}).)*)#\}\s*)?\{%-?\s*macro\s+(?P<sig>\w+\([^)]*\))", re.S)


def _macros_page() -> str:
    text = MACROS.read_text(encoding="utf-8")
    body = ["Shared Jinja macros for app templates. Import the ones a template uses:", "",
            '```jinja\n{% from "components/macros.html" import page_header, card, badge_for %}\n```',
            "", "Macros that call `csrf_field()` (`signout_button`, `session_table`) are imported "
            "`with context`.", ""]
    for m in _MACRO.finditer(text):
        name = m.group("sig").split("(")[0]
        doc = " ".join((m.group("doc") or "").split())
        body += [f"## {name}", "", f"```jinja\n{m.group('sig')}\n```", ""]
        if doc:
            body += [doc, ""]
    return _page("Macros", "The template macros in components/macros.html and their arguments.",
                 60, "lattice/templates/components/macros.html", "\n".join(body),
                 "jinja template macro page_header card badge field")


def _declarations(block: str) -> dict[str, str]:
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    return {m[0]: " ".join(m[1].split()) for m in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block)}


def _tokens_page() -> str:
    css = TOKENS.read_text(encoding="utf-8")
    light = _declarations(css[css.index(":root {"):css.index('[data-mode="dark"]')])
    dark = _declarations(css[css.index('[data-mode="dark"]'):])
    primitives = {k: v for k, v in light.items() if k.startswith("--p-")}

    def resolve(value: str) -> str:
        return re.sub(r"var\((--p-[\w-]+)\)", lambda m: primitives.get(m[1], m[0]), value)

    rows = [[f"`{k}`", f"`{resolve(v)}`", f"`{resolve(dark[k])}`" if k in dark else "same",
             "yes" if ALLOWED_HOST_TOKENS.match(k) else ""]
            for k, v in light.items() if not k.startswith("--p-")]
    body = ["Components style themselves with these tokens (`var(--text-2)`, `var(--sp-3)`), never "
            "with colour values. The dark theme changes the semantic tokens and nothing else, so "
            "anything built from tokens works in both themes.", "",
            "**Host theme** marks the tokens a host's `static/theme.css` may set (ADR 0010). "
            "Primitive tokens (`--p-*`) are private to `tokens.css` and not listed.", "",
            _table(["Token", "Light", "Dark", "Host theme"], rows)]
    return _page("Design tokens", "Every CSS token with its light and dark value, and which a "
                 "host theme may change.", 70, "lattice/static/css/1-settings/tokens.css",
                 "\n".join(body), "css variables colours colors theme dark light brand")


def _slots_and_icons_page() -> str:
    used: dict[str, list[str]] = {}
    for path in sorted(TEMPLATES.rglob("*.html")):
        for name in re.findall(r'slot\("([\w.]+)"\)', path.read_text(encoding="utf-8")):
            used.setdefault(name, []).append(f"`{path.relative_to(TEMPLATES).as_posix()}`")
    body = ["## Slots", "", _first_paragraph(slots.__doc__), "",
            "A host adds a template to a slot with `create_app(slot_templates={name: [template]})`; "
            "an app with `AppManifest(slots={name: \"{key}/template.html\"})`.", "",
            _table(["Slot", "Rendered in"], [[f"`{n}`", ", ".join(used.get(n, []))]
                                            for n in slots.SLOT_NAMES]), "",
            "## Icons", "", _first_paragraph(icons.__doc__), "",
            "The core set:", "", ", ".join(f"`{n}`" for n in sorted(icons.PATHS)) + "."]
    return _page("Slots and icons", "The named slots in the core templates and the core icon set.",
                 80, "lattice/kernel/slots.py` and `lattice/kernel/icons.py", "\n".join(body),
                 "slot icon svg topbar statusbar")


def _index_page() -> str:
    body = ["These pages are generated from the code on every build, so they match the "
            "version you are running. For explanations and examples, start with the "
            "[developer guide](../index.md)."]
    return _page("Reference", "Generated reference for the Python API, settings, command line, "
                 "grid, macros, tokens, slots and icons.", 90, "lattice/reference.py", "\n".join(body))


def pages(parser: argparse.ArgumentParser) -> dict[str, str]:
    """File name -> content for every Reference page."""
    return {"index.md": _index_page(), "api.md": _api_page(), "app-manifest.md": _manifest_page(),
            "grid.md": _grid_page(), "settings.md": _settings_page(), "cli.md": _cli_page(parser),
            "macros.md": _macros_page(), "tokens.md": _tokens_page(),
            "slots-and-icons.md": _slots_and_icons_page()}


def stale(parser: argparse.ArgumentParser) -> list[str]:
    """Pages whose committed file differs from what the code produces (or that are missing)."""
    return [name for name, text in pages(parser).items()
            if not (OUT / name).is_file() or (OUT / name).read_text(encoding="utf-8") != text]


def write(parser: argparse.ArgumentParser) -> list[str]:
    """Write the pages that changed; returns their names."""
    changed = stale(parser)
    OUT.mkdir(parents=True, exist_ok=True)
    generated = pages(parser)
    for name in changed:
        (OUT / name).write_text(generated[name], encoding="utf-8")
    return changed
