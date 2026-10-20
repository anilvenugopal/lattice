"""Ctrl+J: providers, filters, counts, previews, and access rules."""

from pathlib import Path

from lattice.api import sql_queries

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def test_all_providers_with_counts(as_user, claims):
    html = as_user("viewer").get("/_search?q=CLM-26-T").text
    assert 'data-provider="grid.showcase.claims"' in html
    assert '<span class="palette__count">6</span>' in html          # six claims match
    assert "Show all 6 in Claims" in html                       # five shown, one more


def test_filter_by_one_provider(as_user, claims):
    html = as_user("viewer").get("/_search?q=CLM-26-T&provider=grid.showcase.claims").text
    assert html.count("data-palette-item") == 6
    assert '<div class="palette__group">' not in html
    assert 'palette__filter is-active" data-provider="grid.showcase.claims"' in html


def test_empty_query_lists_pages_and_commands(as_user):
    html = as_user("viewer").get("/_search").text
    assert 'href="/showcase/events"' in html and 'data-command="theme-dark"' in html
    assert "/admin/users" not in html


def test_unknown_provider_falls_back_to_all(as_user, claims):
    html = as_user("viewer").get("/_search?q=claim&provider=nope").text
    assert 'palette__filter is-active" data-provider=""' in html


def test_previews_for_record_page_and_command(as_user, claims):
    c = as_user("viewer")
    record = c.get(f"/_search/preview/grid.showcase.claims/{claims[1].id}").text
    assert claims[1].number in record and ">Open</a>" in record
    assert "closePanel()" not in record and "runForPanel" not in record   # read-only
    page = c.get("/_search/preview/pages/events").text
    assert "Events" in page and 'href="/showcase/events/new"' not in page   # needs the permission
    assert 'href="/showcase/events/new"' in as_user("editor").get("/_search/preview/pages/events").text
    command = c.get("/_search/preview/commands/signout").text
    assert "End this session" in command


def test_search_respects_roles_and_row_scoping(as_user, users, db):
    theirs = db.value(CHECK.add_notice, owner_id=users["viewer"].id, subject="Hello viewer")
    c = as_user("editor")
    assert "Hello viewer" not in c.get("/_search?q=hello").text
    assert c.get(f"/_search/preview/grid.showcase.notices/{theirs}").status_code == 404
    assert "Hello viewer" in as_user("viewer").get("/_search?q=hello").text
    viewer = as_user("viewer")
    assert viewer.get("/_search/preview/pages/admin.users").status_code == 404
    assert viewer.get("/_search/preview/nope/1").status_code == 404
