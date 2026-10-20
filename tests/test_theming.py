"""Theming and overrides (ADR 0010): template order, icons, slots, data-app, app and host CSS."""

from contextlib import contextmanager

import pytest
from fastapi import APIRouter, Request
from fastapi.testclient import TestClient

from lattice.components.manifest import AppManifest
from lattice.host import AppError, create_app
from lattice.kernel import css_rules
from lattice.kernel.icons import PATHS, icon
from lattice.kernel.nav import NavNode
from lattice.kernel.web import render_page
from lattice.testing import login

GOOD_APP_CSS = '@layer components { [data-app="notes"] .note { color: var(--text-2); } }'
GOOD_THEME = ('@layer settings { :root { --brand: #0B7A75; } '
              '[data-mode="dark"] { --brand: #3FB8B2; } }')


def notes_app(tmp_path, css=GOOD_APP_CSS, slot_templates=None, extra_template_dir=None, **kw):
    """A small app with one page, its own template folder, static folder and stylesheet."""
    templates = tmp_path / "notes_templates"
    (templates / "notes").mkdir(parents=True)
    (templates / "notes" / "page.html").write_text(
        '{% extends "base/shell.html" %}{% block main %}<p class="note">notes page</p>{% endblock %}')
    for name, body in (slot_templates or {}).items():
        (templates / name).write_text(body)
    if extra_template_dir:
        (templates / extra_template_dir).mkdir()
    static = tmp_path / "notes_static"
    static.mkdir()
    (static / "notes.css").write_text(css)
    router = APIRouter()

    @router.get("/page")
    def page(request: Request):
        return render_page(request, "notes/page.html", "notes")

    return AppManifest(key="notes", label="Notes", routers=[router], templates=templates,
                       static=static, stylesheets=["notes.css"],
                       nav=[NavNode("notes", "Notes", "/notes/page", icon="mail")], **kw)


@contextmanager
def signed_in(web):
    with TestClient(web) as c:
        assert login(c, "viewer@test.io").status_code == 303
        yield c


# ── data-app and app stylesheets ─────────────────────────────────────────────

def test_app_pages_carry_data_app_and_load_app_css(db, users, tmp_path):
    with signed_in(create_app(apps=[notes_app(tmp_path)])) as c:
        page = c.get("/notes/page").text
        assert '<main class="main" id="main" data-app="notes">' in page
        assert '<link rel="stylesheet" href="/static/notes/notes.css">' in page
        assert c.get("/static/notes/notes.css").text == GOOD_APP_CSS
        assert 'data-app=' not in c.get("/account/profile").text.split("<main", 1)[1][:60]


@pytest.mark.parametrize("css, message", [
    ('.note { color: var(--text); }', "@layer components"),
    ('@layer components { .note { color: var(--text); } }', "not scoped"),
    ('@layer components { [data-app="notes"] .n { color: #fff; } }', "colour literal"),
    ('@layer components { [data-app="notes"] .n { color: var(--p-white); } }', "--p-*"),
    ('@layer components { [data-app="notes"] .n { color: var(--text) !important; } }', "!important"),
    ('@layer components { :root { --brand: var(--text); } }', "not scoped"),
])
def test_app_stylesheet_rules(tmp_path, css, message):
    with pytest.raises(AppError, match=message):
        create_app(apps=[notes_app(tmp_path, css=css)])


# ── Templates ────────────────────────────────────────────────────────────────

def test_app_cannot_override_core_templates(tmp_path):
    with pytest.raises(AppError, match="may only contain notes/"):
        create_app(apps=[notes_app(tmp_path, extra_template_dir="auth")])


def test_host_overrides_core_page_and_adds_slot_templates(db, users, tmp_path):
    host = tmp_path / "host"
    (host / "templates" / "auth").mkdir(parents=True)
    (host / "templates" / "host").mkdir()
    (host / "templates" / "auth" / "login.html").write_text("custom sign-in page")
    (host / "templates" / "host" / "banner.html").write_text('<span class="banner">TEST ENV</span>')
    web = create_app(apps=[], host_dir=host, slot_templates={"statusbar.start": "host/banner.html"})
    with TestClient(web) as c:
        assert c.get("/auth/login").text == "custom sign-in page"


def test_host_may_override_only_listed_pages(tmp_path):
    host = tmp_path / "host"
    (host / "templates" / "admin").mkdir(parents=True)
    (host / "templates" / "admin" / "system.html").write_text("x")
    with pytest.raises(AppError, match="may override only"):
        create_app(apps=[], host_dir=host)


# ── Slots ────────────────────────────────────────────────────────────────────

def test_app_slots_render_in_core_templates(db, users, tmp_path):
    app = notes_app(tmp_path, slot_templates={"notes/top.html": '<a class="notes-top">Notes</a>'},
                    slots={"topbar.end": "notes/top.html"})
    with signed_in(create_app(apps=[app])) as c:
        assert '<a class="notes-top">Notes</a>' in c.get("/").text


def test_slot_rules(tmp_path):
    with pytest.raises(ValueError, match="Unknown slot"):
        create_app(apps=[notes_app(tmp_path, slots={"sidebar.top": "notes/page.html"})])
    with pytest.raises(AppError, match="must be in notes/"):
        create_app(apps=[notes_app(tmp_path / "b", slots={"topbar.end": "other/x.html"})])


# ── Icons and help links ─────────────────────────────────────────────────────

def test_app_icons_are_namespaced_and_host_can_replace_core_icons(db, users, tmp_path):
    app = notes_app(tmp_path, icons={"pen": '<path d="M1 1"/>'}, icon="notes:pen",
                    help_url="https://example.test/notes")
    web = create_app(apps=[app], icons_override={"search": '<path d="M2 2"/>'})
    assert '<path d="M1 1"/>' in icon("notes:pen")
    assert '<path d="M2 2"/>' in icon("search") and PATHS["search"] not in icon("search")
    assert icon("pen") == icon("no-such-icon")             # app icons need their prefix
    with signed_in(web) as c:
        assert 'href="https://example.test/notes"' in c.get("/").text


def test_icon_rules(tmp_path):
    with pytest.raises(ValueError, match="replace no core icon"):
        create_app(apps=[], icons_override={"brand-new": "<path/>"})
    with pytest.raises(ValueError, match="must not contain ':'"):
        create_app(apps=[notes_app(tmp_path, icons={"a:b": "<path/>"})])


# ── Host theme ───────────────────────────────────────────────────────────────

def test_host_theme_loads_after_core_css(db, users, tmp_path):
    host = tmp_path / "host"
    (host / "static").mkdir(parents=True)
    (host / "static" / "theme.css").write_text(GOOD_THEME)
    with signed_in(create_app(apps=[], host_dir=host)) as c:
        head = c.get("/").text.split("</head>")[0]
        assert head.index("/static/css/app.css") < head.index("/static/host/theme.css")
        assert c.get("/static/host/theme.css").text == GOOD_THEME


@pytest.mark.parametrize("theme, message", [
    (":root { --brand: #000000; } [data-mode=\"dark\"] { --brand: #FFFFFF; }", "@layer settings"),
    ("@layer settings { :root { --sp-1: 2px; } [data-mode=\"dark\"] { --sp-1: 2px; } }",
     "may not change"),
    ("@layer settings { :root { --brand: #000000; } }", "same tokens"),
    ("@layer settings { :root { --brand: #000; color: red; } [data-mode=\"dark\"] { --brand: #fff; } }",
     "only tokens"),
    ("@layer settings { .btn { --brand: #000; } }", "only :root"),
])
def test_host_theme_rules(theme, message):
    assert any(message in e for e in css_rules.host_theme_errors(theme)), \
        css_rules.host_theme_errors(theme)


# ── App accent, favicon, host fonts and email templates (ADR 0010, as built) ──

def test_an_app_accent_marks_its_rail_entry_and_pages(db, users, tmp_path):
    with signed_in(create_app(apps=[notes_app(tmp_path, accent="warning")])) as c:
        page = c.get("/notes/page").text
        assert 'class="rail__btn is-active accent-warning"' in page
        assert 'class="main accent-warning"' in page
    with pytest.raises(AppError, match="accent 'teal'"):
        create_app(apps=[notes_app(tmp_path / "b", accent="teal")])


def test_the_favicon_setting_replaces_the_logos(db, users, monkeypatch):
    from lattice.kernel.config import settings
    monkeypatch.setattr(settings, "brand_favicon", "/static/host/favicon.ico")
    with signed_in(create_app(apps=[])) as c:
        head = c.get("/").text.split("</head>")[0]
        assert '<link rel="icon" href="/static/host/favicon.ico">' in head
        assert "prefers-color-scheme: light" not in head


@pytest.mark.parametrize("font_face, message", [
    ('@font-face { font-family: "Brand"; src: url("fonts/brand.woff2"); font-display: swap; }', None),
    ('@font-face { font-family: "Brand"; src: url(/static/host/brand.woff2); }', None),
    ('@font-face { font-family: "Brand"; src: url(https://fonts.example.com/b.woff2); }', "host folder"),
    ('@font-face { font-family: "Brand"; color: red; src: url(b.woff2); }', "only font descriptors"),
])
def test_a_host_theme_may_load_its_own_fonts(font_face, message):
    theme = font_face + ' @layer settings { :root { --font-ui: "Brand", sans-serif; } ' \
                        '[data-mode="dark"] { --font-ui: "Brand", sans-serif; } }'
    errors = css_rules.host_theme_errors(theme)
    assert (errors == []) if message is None else any(message in e for e in errors), errors


def test_a_host_rewords_the_notification_emails(db, users, tmp_path):
    from lattice.kernel.services import notifications
    host = tmp_path / "host"
    (host / "templates" / "email").mkdir(parents=True)
    (host / "templates" / "email" / "test.txt").write_text("Greetings from Acme. {{ base }}")
    create_app(apps=[], host_dir=host)
    assert notifications.render_email("test") == "Greetings from Acme. http://localhost:8000\n"
    assert "Open it:" in notifications.render_email("notification", title="T", notification_id=1,
                                                    kind_label="K")
