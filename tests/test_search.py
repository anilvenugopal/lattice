"""Ctrl+J: providers, filters, counts, previews, and access rules."""

from sqlalchemy import select

from lattice.kernel.models import Message


def test_all_providers_with_counts(as_user, items):
    html = as_user("viewer").get("/_search?q=item").text
    assert 'data-provider="grid.demo.work_items"' in html and 'data-provider="pages"' in html
    assert 'data-provider="commands"' in html
    assert '<span class="palette__count">6</span>' in html          # six work items match
    assert "Show all 6 in Work items" in html                       # five shown, one more


def test_filter_by_one_provider(as_user, items):
    html = as_user("viewer").get("/_search?q=item&provider=grid.demo.work_items").text
    assert html.count("data-palette-item") == 6
    assert '<div class="palette__group">' not in html
    assert 'palette__filter is-active" data-provider="grid.demo.work_items"' in html


def test_empty_query_lists_pages_and_commands(as_user, items):
    html = as_user("viewer").get("/_search").text
    assert 'href="/demo/work"' in html and 'data-command="theme-dark"' in html
    assert "/admin/users" not in html


def test_unknown_provider_falls_back_to_all(as_user, items):
    html = as_user("viewer").get("/_search?q=item&provider=nope").text
    assert 'palette__filter is-active" data-provider=""' in html


def test_previews_for_record_page_and_command(as_user, items):
    c = as_user("viewer")
    record = c.get(f"/_search/preview/grid.demo.work_items/{items[1].id}").text
    assert "WI-00002" in record and ">Open</a>" in record
    assert "closePanel()" not in record and "runForPanel" not in record   # read-only
    page = c.get("/_search/preview/pages/work").text
    assert "Work Queue" in page and 'href="/demo/work/new"' in page
    command = c.get("/_search/preview/commands/signout").text
    assert "End this session" in command


def test_search_respects_roles_and_row_scoping(as_user, users, items, db):
    c = as_user("editor")
    other = db.scalar(select(Message.id).where(Message.owner_id == users["viewer"].id))
    assert "Hello viewer" not in c.get("/_search?q=hello").text
    assert c.get(f"/_search/preview/grid.demo.inbox/{other}").status_code == 404
    viewer = as_user("viewer")
    assert viewer.get("/_search/preview/pages/admin.users").status_code == 404
    assert viewer.get("/_search/preview/nope/1").status_code == 404
