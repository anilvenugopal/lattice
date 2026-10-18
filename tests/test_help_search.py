"""Help search: index, ranking, prefixes, roles, snippets; the search page and Ctrl+J source."""

from contextlib import contextmanager
from datetime import datetime

from fastapi.testclient import TestClient

from lattice.components.help import search as help_search
from lattice.components.help.content import HELP, Topic
from lattice.components.manifest import AppManifest
from lattice.host import create_app
from lattice.kernel.auth.sessions import CurrentUser
from lattice.kernel.nav import NavNode
from lattice.testing import login

VIEWER = CurrentUser(id=1, email="v@x", display_name="V", roles=("viewer",),
                     must_change_password=False, has_password=True, session_id="s")


def t(slug, title, text="", keywords="", permission="", summary=""):
    return Topic(app="notes", slug=slug, title=title, summary=summary, order=1, keywords=keywords,
                 permission=permission, html="", toc=[], text=text, updated=datetime(2026, 1, 1))


TOPICS = [
    t("approve", "Approving items", "Select items and choose Approve. Approved items move on."),
    t("assign", "Assigning owners", "To approve faster, assign an owner first."),
    t("export", "Exporting", "Download the list as CSV.", keywords="spreadsheet excel"),
    t("admin", "Approval policy", "Approve rules for admins.", permission="lattice.users.manage"),
]


def test_stemming_and_stop_words():
    assert help_search.tokens("The approving of approved items") == ["approv", "approv", "item"]


def test_title_matches_rank_above_body_matches():
    index = help_search.HelpIndex(TOPICS)
    hits = index.search("approve ", VIEWER)
    assert [h.topic.slug for h in hits] == ["approve", "assign"]


def test_every_word_must_match_and_keywords_count():
    index = help_search.HelpIndex(TOPICS)
    assert [h.topic.slug for h in index.search("approve owner ", VIEWER)] == ["assign"]
    assert [h.topic.slug for h in index.search("excel ", VIEWER)] == ["export"]
    assert index.search("approve nothingmatches ", VIEWER) == []


def test_last_word_matches_as_a_prefix_while_typing():
    index = help_search.HelpIndex(TOPICS)
    assert [h.topic.slug for h in index.search("spread", VIEWER)] == ["export"]
    assert index.search("spread ", VIEWER) == []          # a finished word must match whole


def test_roles_filter_results_and_snippets_mark_matches():
    index = help_search.HelpIndex(TOPICS)
    assert "admin" not in [h.topic.slug for h in index.search("approval", VIEWER)]
    hit = index.search("download", VIEWER)[0]
    assert "<mark>Download</mark>" in hit.snippet


def test_search_text_is_rendered_text_not_markdown(db, users, tmp_path):
    root = tmp_path / "help"
    root.mkdir()
    (root / "index.md").write_text("---\ntitle: N\n---\nUse **bold** `code` and [a link](https://x.io).\n")
    create_app(apps=[AppManifest(key="notes", label="Notes", help=root)])
    assert HELP["notes"].home.text == "Use bold code and a link."


# ── Pages and Ctrl+J ─────────────────────────────────────────────────────────

def notes_app(tmp_path):
    root = tmp_path / "help"
    (root / "guides").mkdir(parents=True)
    (root / "index.md").write_text("---\ntitle: Notes\n---\nNotes help.\n")
    (root / "guides" / "index.md").write_text("---\ntitle: Guides\n---\nGuides.\n")
    (root / "guides" / "sharing.md").write_text(
        "---\ntitle: Sharing notes\nsummary: Send a note to a colleague.\n---\nUse the share button.\n")
    return AppManifest(key="notes", label="Notes", help=root,
                       nav=[NavNode("notes", "Notes", "/notes/x")])


@contextmanager
def signed_in(web):
    with TestClient(web) as c:
        assert login(c, "viewer@test.io").status_code == 303
        yield c


def test_search_page_and_ctrl_j_help_source(db, users, tmp_path):
    with signed_in(create_app(apps=[notes_app(tmp_path)])) as c:
        page = c.get("/help/search?q=share").text
        assert 'href="/help/notes/guides/sharing"' in page and "<mark>share</mark>" in page
        body = c.get("/_search?q=sharing").text
        assert 'data-provider="help"' in body
        assert 'data-preview="/_search/preview/help/notes/guides/sharing"' in body
        preview = c.get("/_search/preview/help/notes/guides/sharing").text
        assert "Sharing notes" in preview and 'href="/help/notes/guides/sharing"' in preview
        assert c.get("/_search/preview/help/notes/nowhere").status_code == 404


def test_every_page_links_to_its_help(db, users, tmp_path):
    with signed_in(create_app(apps=[notes_app(tmp_path)])) as c:
        page = c.get("/account/profile").text
        assert '<body data-nav-key="account.profile">' in page
        assert 'href="/help/for/account.profile"' in page
