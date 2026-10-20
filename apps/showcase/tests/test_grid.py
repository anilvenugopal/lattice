"""The standard grid on the showcase's grids: engine, endpoints, actions, scoping."""

from datetime import date
from pathlib import Path

from lattice.api import sql_queries
from lattice.components.grid import engine
from lattice.testing import current, post_json
from lattice_showcase import claims as claim_pages

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def q(**kw):
    return engine.GridQuery(**kw)


def numbers(page):
    return {r["claim_number"][-1] for r in page.rows}


def test_search_filters_views_sort_and_paging(db, users, claims):
    spec = claim_pages.GRID
    me = current(users["editor"])
    page = engine.fetch_page(spec, db, me, q(q="HO-1", view="all"))
    assert numbers(page) == {"2"}

    page = engine.fetch_page(spec, db, me, q(view="all", filters={"severity": ["minor", "total"]},
                                             sort="estimate"))
    assert [r["claim_number"][-1] for r in page.rows] == ["1", "4", "5"]

    page = engine.fetch_page(spec, db, me, q(view="mine"))
    assert numbers(page) == {"1", "2"}

    page = engine.fetch_page(spec, db, me, q(view="all", size=2, page=99, sort="-estimate"))
    assert page.page == 3 and page.total == 6 and numbers(page) == {"1", "2"}


def test_search_escapes_like_wildcards(db, users, claims):
    page = engine.fetch_page(claim_pages.GRID, db, current(users["admin"]), q(q="%", view="all"))
    assert page.total == 0


def test_rows_endpoint_renders_and_keeps_state(as_user, claims):
    c = as_user("viewer")
    html = c.get("/_grid/showcase.claims/rows?view=all&f_status=inspected").text
    assert html.count("<tr data-id") == 1 and claims[2].number in html


def test_action_skips_ineligible_rows_and_audits_each_row(as_user, claims, db):
    c = as_user("editor")
    ids = [x.id for x in claims[:4]]           # new, assigned, inspected, settled
    body = post_json(c, "/_grid/showcase.claims/action/inspected", {"ids": ids}).json()
    assert "inspection of 2" in body["message"] and "2 skipped" in body["message"]
    assert [db.one(CHECK.claim, id=i)["status"] for i in ids] == ["inspected"] * 3 + ["settled"]
    events = db.all(CHECK.audit_events, action="showcase.claims.inspected")
    assert sorted(e["target_id"] for e in events) == sorted(str(i) for i in ids[:2])


def test_action_permissions_and_required_fields(as_user, claims):
    viewer = as_user("viewer")
    resp = post_json(viewer, "/_grid/showcase.claims/action/prioritise", {"ids": [claims[0].id]})
    assert resp.status_code == 403
    editor = as_user("editor")
    resp = post_json(editor, "/_grid/showcase.claims/action/assign_zone",
                     {"ids": [claims[0].id], "values": {}})
    assert resp.status_code == 400 and "Zone" in resp.json()["detail"]


def test_action_on_all_matching_rows(as_user, claims, db):
    c = as_user("admin")
    resp = post_json(c, "/_grid/showcase.claims/action/take",
                     {"all": True, "params": "view=all&f_status=new", "values": {}})
    assert "2 claim(s)" in resp.json()["message"]
    admin = db.one(CHECK.claim, id=claims[5].id)["handler_id"]
    assert {db.one(CHECK.claim, id=claims[i].id)["handler_id"] for i in (0, 4)} == {admin}


def test_query_scopes_rows_per_user(as_user, users, claims, db):
    theirs = db.value(CHECK.add_notice, owner_id=users["viewer"].id, subject="For the viewer")
    c = as_user("editor")
    assert c.get(f"/_grid/showcase.notices/panel/{theirs}").status_code == 404
    assert post_json(c, "/_grid/showcase.notices/action/read", {"ids": [theirs]}).status_code == 400
    assert not db.one(CHECK.notice, id=theirs)["is_read"]
    assert "For the viewer" not in c.get("/_grid/showcase.notices/rows?view=all").text
    assert c.get(f"/showcase/notices/{theirs}", follow_redirects=False).status_code == 404


def test_opening_a_notice_marks_it_read(as_user, users, claims, db):
    mine = db.value(CHECK.add_notice, owner_id=users["editor"].id, subject="Mine")
    res = as_user("editor").get(f"/showcase/notices/{mine}", follow_redirects=False)
    assert res.status_code == 303 and db.one(CHECK.notice, id=mine)["is_read"]


def test_column_preferences_and_export(as_user, users, claims, db):
    c = as_user("viewer")
    resp = post_json(c, "/_grid/showcase.claims/columns",
                     {"hidden": ["surveyor", "claim_number", "bogus"]})
    assert resp.json()["hidden"] == ["surveyor"]          # required and unknown columns ignored
    pref = db.one(CHECK.preference, user_id=users["viewer"].id, key="grid.showcase.claims.hidden")
    assert pref["value"] == ["surveyor"]
    assert ">Surveyor<" not in c.get("/_grid/showcase.claims/rows").text

    csv = c.get("/_grid/showcase.claims/export.csv?view=all&f_status=new").text.splitlines()
    assert csv[0].startswith("Claim,Insured") and len(csv) == 3
    assert c.get("/_grid/showcase.intake/export.csv").status_code == 404   # export=False


def test_action_rejects_values_outside_field_options(as_user, claims, db):
    editor = as_user("editor")
    resp = post_json(editor, "/_grid/showcase.claims/action/assign_zone",
                     {"ids": [claims[0].id], "values": {"zone_id": "999"}})
    assert resp.status_code == 400 and "Invalid value for Zone" in resp.json()["detail"]
    assert db.one(CHECK.claim, id=claims[0].id)["zone_id"] is None
    admin = as_user("admin")
    resp = post_json(admin, "/_grid/users/action/grant", {"ids": [1], "values": {"role": "root"}})
    assert resp.status_code == 400


def test_values_that_do_not_fit_the_column_match_nothing(as_user, claims):
    c = as_user("viewer")
    assert c.get("/_grid/showcase.claims/panel/abc").status_code == 404
    html = c.get("/_grid/showcase.claims/rows?view=all&x_event_id=abc").text
    assert "<tr data-id" not in html
    resp = post_json(as_user("editor"), "/_grid/showcase.claims/action/inspected", {"ids": ["abc"]})
    assert resp.status_code == 400


def test_secondary_line_uses_its_own_column_labels(as_user, claims):
    html = as_user("viewer").get("/_grid/showcase.claims/rows?view=all").text
    assert '<div class="dg__secondary">Phone</div>' in html


# ── Fixed filters: a grid embedded in another page ───────────────────────────

def test_fixed_filter_narrows_rows_and_combines_with_search(db, users, claims):
    spec = claim_pages.GRID
    me = current(users["editor"])
    live = db.one(CHECK.claim_event, id=claims[0].id)["event_id"]
    page = engine.fetch_page(spec, db, me, q(view="all", fixed={"event_id": [str(live)]}))
    assert page.total == 4
    page = engine.fetch_page(spec, db, me, q(view="all", q="HO-3",
                                             fixed={"event_id": [str(live)]}))
    assert numbers(page) == {"4"}


def test_fixed_filter_travels_with_rows_actions_and_export(as_user, claims):
    c = as_user("editor")
    body = c.get("/_grid/showcase.claims/rows?view=all&x_event_code=CAT-T02").text
    assert claims[4].number in body and claims[0].number not in body
    csv_text = c.get("/_grid/showcase.claims/export.csv?view=all&x_event_code=CAT-T02").text
    assert claims[5].number in csv_text and claims[0].number not in csv_text
    resp = post_json(c, "/_grid/showcase.claims/action/inspected",
                     {"all": True, "params": "view=all&x_event_code=CAT-T02"}).json()
    assert "inspection of 1 " in resp["message"]          # the closed event's new claim only


def test_unknown_fixed_column_is_a_bad_request(as_user, claims):
    c = as_user("editor")
    assert c.get("/_grid/showcase.claims/rows?x_nope=1").status_code == 400
    assert c.get("/_grid/showcase.claims/export.csv?x_nope=1").status_code == 400


def test_embedded_grid_on_the_loss_page(as_user, claims, db):
    event_id = db.one(CHECK.claim_event, id=claims[0].id)["event_id"]
    page = as_user("editor").get(f"/showcase/events/{event_id}/loss").text
    assert f'<input type="hidden" name="x_event_id" value="{event_id}">' in page
    assert '"syncUrl": false' in page                           # the page URL is left alone


def test_a_narrowing_in_the_url_shows_as_a_removable_chip(as_user, claims):
    # The event page's claims calendar, clicked on 3 October, opens this.
    page = as_user("viewer").get("/showcase/claims?x_event_code=CAT-T02&x_reported_at=2026-10-03").text
    assert '"label": "Event: CAT-T02"' in page and '"label": "Reported: 3 Oct 2026"' in page
    assert '<input type="hidden" name="x_event_code" value="CAT-T02" data-narrow>' in page
    rows = as_user("viewer").get("/_grid/showcase.claims/rows?view=all&x_reported_at=2026-10-03").text
    assert rows.count("<tr data-id") == 6


def test_the_event_timeline_windows_bars_and_markers(as_user, claims, db):
    closed = db.one(CHECK.claim_event, id=claims[4].id)["event_id"]
    db.run(CHECK.close_event, id=closed, closed_on=date(2026, 10, 5))
    c = as_user("viewer")
    url = "/_timeline/showcase.event_timeline/data"
    every = c.get(url).json()["bars"]
    assert {b["label"] for b in every if b["href"].endswith(f"/{closed}")} == {"Watch", "Response", "Closed"}
    # Inside the response: the watch ended before, and the closing marker comes after.
    window = c.get(url, params={"from": "2026-10-03T12:00:00Z", "to": "2026-10-04T00:00:00Z"}).json()
    assert {b["label"] for b in window["bars"] if b["href"].endswith(f"/{closed}")} == {"Response"}
