"""Ctrl+J with no apps installed: the Pages and Commands providers, previews, access."""


def test_empty_query_lists_pages_and_commands(as_user):
    html = as_user("viewer").get("/_search").text
    assert 'data-provider="pages"' in html and 'data-provider="commands"' in html
    assert 'href="/account/preferences"' in html and 'data-command="theme-dark"' in html
    assert "/admin/users" not in html


def test_filter_by_one_provider_and_unknown_provider(as_user):
    c = as_user("viewer")
    html = c.get("/_search?q=theme&provider=commands").text
    # Three theme commands, and "Open preferences", whose description mentions the theme.
    assert html.count("data-palette-item") == 4
    assert 'palette__filter is-active" data-provider="commands"' in html
    html = c.get("/_search?q=theme&provider=nope").text
    assert 'palette__filter is-active" data-provider=""' in html


def test_page_and_command_previews(as_user):
    c = as_user("admin")
    page = c.get("/_search/preview/pages/admin").text
    assert "Administration" in page and 'href="/admin/roles"' in page
    assert "End this session" in c.get("/_search/preview/commands/signout").text


def test_previews_respect_roles(as_user):
    viewer = as_user("viewer")
    assert viewer.get("/_search/preview/pages/admin.users").status_code == 404
    assert viewer.get("/_search/preview/nope/1").status_code == 404
