"""Migrating loads the places once; search finds towns, counties and zip codes."""

import refdata


def test_migrate_loads_the_places_once(engine, migrated):
    assert migrated[0] == "0001_place.sql" and migrated[1].startswith("places (")
    assert int(migrated[1][8:-1]) > 60_000
    assert refdata.migrate(engine) == []                  # nothing pending the second time


def test_a_town_by_name_and_state(conn):
    [first, *_] = refdata.search_places(conn, "Lake Charles, LA")
    assert (first["label"], first["kind"]) == ("Lake Charles, LA", "place")
    assert abs(first["lon"] + 93.21) < 0.1 and abs(first["lat"] - 30.2) < 0.1


def test_larger_towns_first_and_an_exact_name_before_a_prefix(conn):
    houstons = refdata.search_places(conn, "Houston")
    assert houstons[0]["label"] == "Houston, TX"
    assert all(p["name"].lower().startswith("houston") for p in houstons)


def test_counties_and_zip_codes(conn):
    assert refdata.search_places(conn, "Harris County, TX")[0]["kind"] == "county"
    assert refdata.search_places(conn, "77002")[0]["label"] == "ZIP 77002"


def test_short_or_odd_text_finds_nothing_and_fails_nothing(conn):
    assert refdata.search_places(conn, "a") == []
    assert refdata.search_places(conn, "100%_") == []
