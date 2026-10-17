"""In-app help: loading, rendering, page map, contextual help, access, assets."""

from contextlib import contextmanager

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from lattice.components.help.content import HELP, HelpError, parse_front_matter
from lattice.components.manifest import AppManifest
from lattice.host import AppError, create_app
from lattice.kernel.nav import NavNode
from lattice.testing import login


def write(root, files: dict[str, str]):
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return root


def topic(title, body="", extra=""):
    return f"---\ntitle: {title}\n{extra}---\n\n{body}\n"


BASIC = {
    "index.md": topic("Notes", "Start with [writing](writing.md) or [sections](more/index.md).",
                      "summary: Notes help home.\n"),
    "writing.md": topic("Writing notes", "## Save a note\n\nPress save.\n\n## `Share`\n\nUse share.",
                        "order: 2\nkeywords: compose draft\n"),
    "more/index.md": topic("More", "A section.", "order: 5\n"),
    "more/advanced.md": topic("Advanced", "![diagram](../images/d.png) Back to [home](../index.md).",
                              "order: 1\n"),
    "secret.md": topic("Admin only", "Hidden.", "roles: [admin]\norder: 9\n"),
    "images/d.png": "PNGDATA",
    "help.toml": '[pages]\n"notes" = "writing#save-a-note"\n"notes.other" = "index"\n',
}


def notes_app(tmp_path, files=BASIC):
    router = APIRouter()
    return AppManifest(key="notes", label="Notes", routers=[router],
                       help=write(tmp_path / "help", files),
                       nav=[NavNode("notes", "Notes", "/notes/x"),
                            NavNode("notes.other", "Other", "/notes/y", parent="notes")])


@contextmanager
def signed_in(web, who="viewer@test.io"):
    with TestClient(web) as c:
        assert login(c, who).status_code == 303
        yield c


# ── Loading and rendering ────────────────────────────────────────────────────

def test_topics_load_with_sections_order_links_and_toc(db, users, tmp_path):
    create_app(apps=[notes_app(tmp_path)])
    notes = HELP["notes"]
    assert set(notes.topics) == {"", "writing", "more", "more/advanced", "secret"}
    home = notes.topics[""].html
    assert 'href="/help/notes/writing"' in home and 'href="/help/notes/more"' in home
    advanced = notes.topics["more/advanced"].html
    assert 'src="/help/notes/_assets/images/d.png"' in advanced and 'href="/help/notes"' in advanced
    assert notes.topics["writing"].toc == [(2, "save-a-note", "Save a note"), (2, "share", "Share")]


def test_callouts_code_and_mermaid_render(db, users, tmp_path):
    files = dict(BASIC)
    files["writing.md"] = topic("Writing", "> [!WARNING]\n> Careful.\n\n"
                                "```python\ndef f():\n    return 1\n```\n\n"
                                "```mermaid\ngraph LR; A-->B\n```")
    files["help.toml"] = ""
    create_app(apps=[notes_app(tmp_path, files)])
    html = HELP["notes"].topics["writing"].html
    assert 'class="callout tone-warning" data-label="Warning"' in html and "[!WARNING]" not in html
    assert '<pre class="code"><code class="language-python"><span class="k">def</span>' in html
    assert '<pre class="mermaid">graph LR; A--&gt;B\n</pre>' in html


@pytest.mark.parametrize("change, message", [
    ({"index.md": None}, "no index.md"),
    ({"writing.md": "no front matter"}, "missing front matter"),
    ({"writing.md": "---\nsummary: x\n---\nbody"}, "needs a title"),
    ({"writing.md": topic("W", "[gone](missing.md)")}, "points to no topic"),
    ({"writing.md": topic("W", "[up](../../x.md)")}, "leaves the help folder"),
    ({"help.toml": '[pages]\n"admin.users" = "writing"\n'}, "not a page of this app"),
    ({"help.toml": '[pages]\n"notes" = "nowhere"\n'}, "which is no topic"),
    ({"help.toml": '[pages]\n"notes" = "writing#no-such-heading"\n'}, "no heading"),
])
def test_help_rules_stop_the_host(tmp_path, change, message):
    files = {k: v for k, v in {**BASIC, **change}.items() if v is not None}
    with pytest.raises(AppError, match=message):
        create_app(apps=[notes_app(tmp_path, files)])


def test_front_matter_lists_and_comments():
    meta, body = parse_front_matter("---\ntitle: T\n# note\nroles: [admin, editor]\n---\nBody", "x")
    assert meta == {"title": "T", "roles": ("admin", "editor")} and body == "Body"
    with pytest.raises(HelpError, match="not closed"):
        parse_front_matter("---\ntitle: T\n", "x")


# ── Pages ────────────────────────────────────────────────────────────────────

def test_topic_page_tree_pager_and_toc(db, users, tmp_path):
    with signed_in(create_app(apps=[notes_app(tmp_path)])) as c:
        page = c.get("/help/notes/writing").text
        assert "<h1 class=\"help__title\">Writing notes</h1>" in page
        assert 'class="help-tree__link is-active" href="/help/notes/writing"' in page
        assert 'href="#save-a-note"' in page                        # On this page
        assert 'class="help__prev" href="/help/notes"' in page     # reading order: home, writing, more
        assert 'class="help__next" href="/help/notes/more"' in page
        assert "Advanced" in c.get("/help/notes/more").text          # section page lists its topics


def test_role_restricted_topics_are_hidden(db, users, tmp_path):
    web = create_app(apps=[notes_app(tmp_path)])
    with signed_in(web) as c:
        assert c.get("/help/notes/secret").status_code == 404
        assert "Admin only" not in c.get("/help/notes").text
    with signed_in(web, "admin@test.io") as c:
        assert c.get("/help/notes/secret").status_code == 200


def test_help_for_page_uses_the_map_then_the_app_home(db, users, tmp_path):
    with signed_in(create_app(apps=[notes_app(tmp_path)])) as c:
        assert c.get("/help/for/notes", follow_redirects=False).headers["location"] == \
            "/help/notes/writing#save-a-note"
        assert c.get("/help/for/notes.other", follow_redirects=False).headers["location"] == "/help/notes"
        assert c.get("/help/for/admin.users", follow_redirects=False).headers["location"] == "/help/lattice"
        assert c.get("/help/for/unknown", follow_redirects=False).headers["location"] == "/help"


def test_help_center_lists_apps_then_lattice(db, users, tmp_path):
    with signed_in(create_app(apps=[notes_app(tmp_path)])) as c:
        page = c.get("/help").text
        assert page.index('href="/help/notes"') < page.index('href="/help/lattice"')


def test_assets_are_served_only_from_the_help_folder(db, users, tmp_path):
    (tmp_path / "outside.txt").write_text("secret")
    with signed_in(create_app(apps=[notes_app(tmp_path)])) as c:
        assert c.get("/help/notes/_assets/images/d.png").content == b"PNGDATA"
        assert c.get("/help/notes/_assets/../../outside.txt").status_code == 404
        assert c.get("/help/notes/_assets/writing.md").status_code == 404
        assert c.get("/help/nowhere").status_code == 404
