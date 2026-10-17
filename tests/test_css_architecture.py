"""Enforces the five-layer CSS architecture described in app/static/css/app.css."""

import re
from pathlib import Path

import pytest

CSS = Path("app/static/css")
LAYERS = {"1-settings": "settings", "2-base": "base", "3-layout": "layout",
          "4-components": "components", "5-utilities": "utilities"}
COLOR_LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\(|:\s*(?:white|black|red|blue|green|gray|grey)\b")


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def sheets() -> list[Path]:
    return sorted(p for p in CSS.rglob("*.css") if p.name != "app.css")


def selectors(text: str) -> list[str]:
    """Selector lists of style rules, skipping at-rule preludes and keyframe steps."""
    out = []
    for m in re.finditer(r"([^{};]+)\{", strip_comments(text)):
        sel = m.group(1).strip()
        if sel.startswith("@") or sel in ("from", "to") or re.fullmatch(r"[\d.%,\s]+", sel):
            continue
        out.append(sel)
    return out


def test_every_sheet_is_imported_once_into_its_folder_layer():
    app = strip_comments((CSS / "app.css").read_text())
    imports = re.findall(r'@import url\("([^"]+)"\) layer\((\w+)\);', app)
    assert re.search(r"@layer settings, base, layout, components, utilities;", app)
    imported = [path for path, _ in imports]
    assert sorted(imported) == sorted(str(p.relative_to(CSS)) for p in sheets())
    assert len(imported) == len(set(imported))
    for path, layer in imports:
        assert LAYERS[path.split("/")[0]] == layer, path


@pytest.mark.parametrize("sheet", sheets(), ids=str)
def test_colour_literals_and_primitives_only_in_settings(sheet):
    if sheet.parent.name == "1-settings":
        return
    text = strip_comments(sheet.read_text())
    assert not COLOR_LITERAL.search(text), f"colour literal in {sheet}; add a token"
    assert "var(--p-" not in text, f"primitive token in {sheet}; use a semantic token"


@pytest.mark.parametrize("sheet", sheets(), ids=str)
def test_important_only_in_utilities(sheet):
    if sheet.parent.name != "5-utilities":
        assert "!important" not in strip_comments(sheet.read_text()), sheet


def test_settings_define_only_custom_properties():
    for sheet in (CSS / "1-settings").glob("*.css"):
        for decl in re.findall(r"([\w-]+)\s*:", re.sub(r"[^{}]*\{|\}", ";", strip_comments(sheet.read_text()))):
            assert decl.startswith("--") or decl == "color-scheme", f"{sheet}: {decl}"


def test_base_has_no_class_selectors():
    for sheet in (CSS / "2-base").glob("*.css"):
        for sel in selectors(sheet.read_text()):
            assert not re.search(r"\.[A-Za-z_-]", sel), f"{sheet}: {sel}"


def test_utilities_are_prefixed():
    for sheet in (CSS / "5-utilities").glob("*.css"):
        for sel in selectors(sheet.read_text()):
            assert sel == "[x-cloak]" or re.fullmatch(r"\.u-[a-z0-9-]+", sel), f"{sheet}: {sel}"
