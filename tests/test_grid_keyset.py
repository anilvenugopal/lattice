"""Keyset paging (ADR 0008): Next and Previous carry a cursor, and walking every page that way
gives exactly the rows offset paging gives, whatever the sort, ties and nulls."""

from pathlib import Path

import pytest

from lattice.api import AppManifest, Column, GridSpec, sql_queries
from lattice.components.grid import engine
from lattice.testing import current

CHECK = sql_queries(Path(__file__).parent / "sql").checks
GRID = GridSpec(key="pages.rows", title="Rows", path="/pages", query=CHECK.keyset_rows,
                columns=[Column("name", "Name"), Column("rank", "Rank"),
                         Column("amount", "Amount"), Column("made_at", "Made")])
SORTS = ["name", "-name", "rank", "-rank", "amount", "-amount", "made_at", "-made_at", "id", "-id"]


@pytest.fixture
def host_apps():
    return [AppManifest(key="pages", label="Pages", grids=[GRID])]


def ids(page):
    return [r["id"] for r in page.rows]


def by_offset(db, me, sort):
    pages, n = [], 1
    while True:
        page = engine.fetch_page(GRID, db, me, engine.GridQuery(sort=sort, size=5, page=n))
        pages.append(ids(page))
        if n >= page.pages:
            return pages
        n += 1


@pytest.mark.parametrize("sort", SORTS)
def test_walking_forward_and_back_matches_offset_paging(db, users, sort):
    me = current(users["admin"])
    expected = by_offset(db, me, sort)
    assert len(expected) == 5 and sorted(sum(expected, [])) == list(range(1, 24))

    page = engine.fetch_page(GRID, db, me, engine.GridQuery(sort=sort, size=5))
    forward = [ids(page)]
    while page.next:
        page = engine.fetch_page(GRID, db, me, engine.GridQuery(
            sort=sort, size=5, page=page.page + 1, after=page.next))
        forward.append(ids(page))
    assert forward == expected

    backward = [ids(page)]
    while page.previous:
        page = engine.fetch_page(GRID, db, me, engine.GridQuery(
            sort=sort, size=5, page=page.page - 1, before=page.previous))
        backward.append(ids(page))
    assert backward[::-1] == expected


def test_a_cursor_reads_the_rows_past_it(db, users):
    me = current(users["admin"])
    after_five = engine.cursor({"id": 5}, "id")
    page = engine.fetch_page(GRID, db, me, engine.GridQuery(sort="id", size=5, page=2,
                                                            after=after_five))
    assert ids(page) == [6, 7, 8, 9, 10] and page.previous and page.next


def test_a_broken_cursor_is_refused_and_page_one_ignores_one(db, users):
    me = current(users["admin"])
    with pytest.raises(ValueError, match="out of date"):
        engine.fetch_page(GRID, db, me, engine.GridQuery(sort="rank", size=5, page=2,
                                                         after="not-a-cursor"))
    first = engine.fetch_page(GRID, db, me, engine.GridQuery(sort="id", size=5, after="x"))
    assert ids(first) == [1, 2, 3, 4, 5]
