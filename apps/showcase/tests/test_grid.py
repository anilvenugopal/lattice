"""The standard grid on the showcase app's grids: engine, endpoints, actions, scoping."""

from pathlib import Path

from lattice.api import sql_queries
from lattice.components.grid import engine
from lattice.testing import current, post_json
from lattice_showcase import inbox
from lattice_showcase import items as item_pages

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def q(**kw):
    return engine.GridQuery(**kw)


def test_search_filters_views_sort_and_paging(db, users, items):
    spec = item_pages.GRID
    me = current(users["editor"])
    page = engine.fetch_page(spec, db, me, q(q="item alpha", view="all"))
    assert {r["ref"] for r in page.rows} == {"IT-0001", "IT-0003", "IT-0005"}

    page = engine.fetch_page(spec, db, me, q(filters={"status": ["new", "blocked"]}, sort="amount"))
    assert [r["ref"] for r in page.rows] == ["IT-0001", "IT-0004", "IT-0005", "IT-0006"]

    page = engine.fetch_page(spec, db, me, q(view="mine"))
    assert {r["ref"] for r in page.rows} == {"IT-0001", "IT-0002"}

    page = engine.fetch_page(spec, db, me, q(size=2, page=99, sort="-amount"))
    assert page.page == 3 and page.total == 6 and [r["ref"] for r in page.rows] == ["IT-0002", "IT-0001"]


def test_search_escapes_like_wildcards(db, users, items):
    page = engine.fetch_page(item_pages.GRID, db, current(users["admin"]), q(q="%"))
    assert page.total == 0


def test_rows_endpoint_renders_and_keeps_state(as_user, items):
    c = as_user("viewer")
    html = c.get("/_grid/showcase.items/rows?view=all&f_status=done").text
    assert html.count("<tr data-id") == 1 and "IT-0003" in html


def test_action_skips_ineligible_rows_and_audits_each_row(as_user, items, db):
    c = as_user("editor")
    ids = [i.id for i in items[:4]]           # new, active, done, blocked
    resp = post_json(c, "/_grid/showcase.items/action/complete", {"ids": ids})
    body = resp.json()
    assert "Completed 2" in body["message"] and "2 skipped" in body["message"]
    assert [db.one(CHECK.item, id=i)["status"] for i in ids] == ["new"] + ["done"] * 3
    events = db.all(CHECK.audit_events, action="showcase.items.complete")
    assert sorted(e["target_id"] for e in events) == sorted(str(i) for i in (ids[1], ids[3]))


def test_action_roles_and_required_fields(as_user, items):
    viewer = as_user("viewer")
    assert post_json(viewer, "/_grid/showcase.items/action/delete", {"ids": [1]}).status_code == 403
    editor = as_user("editor")
    resp = post_json(editor, "/_grid/showcase.items/action/status", {"ids": [1], "values": {}})
    assert resp.status_code == 400 and "Status" in resp.json()["detail"]


def test_action_on_all_matching_rows(as_user, items, users, db):
    c = as_user("editor")
    resp = post_json(c, "/_grid/showcase.items/action/assign", {
        "all": True, "params": "view=all&f_status=new", "values": {"owner_id": str(users["viewer"].id)}})
    assert "Assigned 3" in resp.json()["message"]
    owners = {r["owner_id"] for r in db.all(CHECK.owners_with_status, status="new")}
    assert owners == {users["viewer"].id}


def test_query_scopes_rows_per_user(as_user, items, users, db):
    viewer_msg = db.value(CHECK.first_message_of, owner_id=users["viewer"].id)
    c = as_user("editor")
    assert c.get(f"/_grid/showcase.inbox/panel/{viewer_msg}").status_code == 404
    resp = post_json(c, "/_grid/showcase.inbox/action/delete", {"ids": [viewer_msg]})
    assert resp.status_code == 400
    assert db.first(CHECK.message, id=viewer_msg) is not None
    assert "Hello viewer" not in c.get("/_grid/showcase.inbox/rows").text


def test_opening_unread_message_marks_it_read_and_refreshes(as_user, users, items, db):
    msg = db.value(CHECK.first_message_of, owner_id=users["editor"].id)
    c = as_user("editor")
    resp = c.get(f"/_grid/showcase.inbox/panel/{msg}")
    assert "gridrefresh" in resp.headers.get("HX-Trigger", "")
    assert db.one(CHECK.message, id=msg)["is_read"]
    assert inbox.GRID.row_class({"is_read": False}) == "is-unread"


def test_column_preferences_and_export(as_user, users, items, db):
    c = as_user("viewer")
    resp = post_json(c, "/_grid/showcase.items/columns", {"hidden": ["owner", "ref", "bogus"]})
    assert resp.json()["hidden"] == ["owner"]            # required and unknown columns ignored
    pref = db.one(CHECK.preference, user_id=users["viewer"].id, key="grid.showcase.items.hidden")
    assert pref["value"] == ["owner"]
    assert ">Owner<" not in c.get("/_grid/showcase.items/rows").text

    csv = c.get("/_grid/showcase.items/export.csv?view=all&f_status=new").text.splitlines()
    assert csv[0].startswith("starred,Ref,Name") and len(csv) == 4
    assert c.get("/_grid/showcase.inbox/export.csv").status_code == 404   # export=False


def test_action_rejects_values_outside_field_options(as_user, items, db):
    editor = as_user("editor")
    resp = post_json(editor, "/_grid/showcase.items/action/status",
                     {"ids": [items[0].id], "values": {"status": "hacked"}})
    assert resp.status_code == 400 and "Invalid value for Status" in resp.json()["detail"]
    assert db.one(CHECK.item, id=items[0].id)["status"] == "new"
    admin = as_user("admin")
    resp = post_json(admin, "/_grid/users/action/grant", {"ids": [1], "values": {"role": "root"}})
    assert resp.status_code == 400
    resp = post_json(editor, "/_grid/showcase.items/action/assign",
                     {"ids": [items[0].id], "values": {"owner_id": "999"}})
    assert resp.status_code == 400


def test_values_that_do_not_fit_the_column_match_nothing(as_user, items):
    c = as_user("viewer")
    assert c.get("/_grid/showcase.items/panel/abc").status_code == 404
    html = c.get("/_grid/showcase.items/rows?view=all&f_owner_id=abc").text
    assert "<tr data-id" not in html
    resp = post_json(as_user("editor"), "/_grid/showcase.items/action/complete", {"ids": ["abc"]})
    assert resp.status_code == 400


def test_secondary_line_uses_its_own_column_labels(as_user, db, users):
    db.value(CHECK.add_job, name="Nightly", job_type="sync", status="queued")
    html = as_user("viewer").get("/_grid/showcase.jobs/rows").text
    assert '<div class="dg__secondary">Sync</div>' in html


# ── Fixed filters: a grid embedded in another page ───────────────────────────

def test_fixed_filter_narrows_rows_and_combines_with_search(db, users, items):
    spec = item_pages.GRID
    me = current(users["editor"])
    page = engine.fetch_page(spec, db, me, q(view="all", fixed={"category": ["software"]}))
    assert {r["category"] for r in page.rows} == {"software"} and page.total == 3
    page = engine.fetch_page(spec, db, me, q(view="all", q="beta", fixed={"category": ["software"]}))
    assert {r["ref"] for r in page.rows} == {"IT-0004", "IT-0006"}


def test_fixed_filter_travels_with_rows_actions_and_export(as_user, items):
    c = as_user("editor")
    body = c.get("/_grid/showcase.items/rows?view=all&x_category=hardware").text
    assert "IT-0001" in body and "IT-0004" not in body
    csv_text = c.get("/_grid/showcase.items/export.csv?view=all&x_category=hardware").text
    assert "Hardware" in csv_text and "Software" not in csv_text
    resp = post_json(c, "/_grid/showcase.items/action/complete",
                     {"all": True, "params": "view=all&x_category=software"}).json()
    assert resp["message"].startswith("Completed 1 item(s).")    # software's blocked item only


def test_unknown_fixed_column_is_a_bad_request(as_user, items):
    c = as_user("editor")
    assert c.get("/_grid/showcase.items/rows?x_nope=1").status_code == 400
    assert c.get("/_grid/showcase.items/export.csv?x_nope=1").status_code == 400


def test_embedded_grid_on_the_detail_page(as_user, items):
    page = as_user("editor").get("/showcase/items/1?q=zzz&view=closed").text
    assert '<input type="hidden" name="x_category" value="hardware">' in page
    assert "IT-0002" in page and "IT-0004" not in page       # hardware's items, not software's
    assert '"syncUrl": false' in page                           # the page URL is left alone
