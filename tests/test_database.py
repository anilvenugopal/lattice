"""Named SQL files, the migration runner, Db, and one transaction per request."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from lattice.kernel import database
from lattice.kernel.database import Db, NotFound, get_db
from lattice.kernel.migrate import migrate, sources_for
from lattice.kernel.sql import Query, SqlError, parse, sql_queries


def write(tmp_path, body, name="things"):
    folder = tmp_path / "pkg" / "sql"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.sql").write_text(body)
    return folder


GOOD = """-- Things: a test area.

-- name: by_code
-- The role with this code.
SELECT code, label FROM lattice.role WHERE code = :code;

-- name: add
-- A new role.
INSERT INTO lattice.role (code, label) VALUES (:code, :label);

-- name: codes_in
-- Roles whose code is in the list.
SELECT code FROM lattice.role WHERE code = ANY(:codes) ORDER BY code;

-- name: count
-- How many roles there are.
SELECT count(*) FROM lattice.role;

-- name: set_pref
-- Store a JSON preference.
INSERT INTO lattice.user_preference (user_id, key, value) VALUES (:user_id, :key, :value)
"""


# ── Loading named queries (no database needed) ───────────────────────────────

def test_queries_load_by_area_and_name_with_a_traceable_tag(tmp_path):
    sql = sql_queries(write(tmp_path, GOOD))
    q = sql.things.by_code
    assert isinstance(q, Query) and q.key == "pkg/things.by_code"
    assert q.description == "The role with this code." and q.line == 3
    assert q.sql == "SELECT code, label FROM lattice.role WHERE code = :code"
    assert str(q.statement).startswith("/* pkg/things.by_code */ SELECT")
    assert [x.key.split(".")[-1] for x in sql] == ["by_code", "add", "codes_in", "count", "set_pref"]


def test_missing_areas_and_queries_name_the_file(tmp_path):
    sql = sql_queries(write(tmp_path, GOOD))
    with pytest.raises(SqlError, match="no query named 'nope'"):
        _ = sql.things.nope
    with pytest.raises(SqlError, match="no file other.sql"):
        _ = sql.other


@pytest.mark.parametrize("body, message", [
    ("SELECT 1;", "no queries"),
    ("SELECT 1;\n-- name: a\n-- A.\nSELECT 1;", "SQL before the first"),
    ("-- name: Bad-Name\n-- A.\nSELECT 1;", "lower_case_with_underscores"),
    ("-- name: a\n-- A.\nSELECT 1;\n-- name: a\n-- Again.\nSELECT 2;", "defined twice"),
    ("-- name: a\nSELECT 1;", "needs a '--' comment"),
    ("-- name: a\n-- Nothing.\n", "has no SQL"),
    ("-- name: a\n-- Cast.\nSELECT :d::date;", r"write CAST\(:d AS …\)"),
])
def test_file_rules(tmp_path, body, message):
    path = tmp_path / "x.sql"
    path.write_text(body)
    with pytest.raises(SqlError, match=message):
        parse(path, "pkg")


def test_column_casts_are_fine(tmp_path):
    path = tmp_path / "x.sql"
    path.write_text("-- name: a\n-- Cast a column.\nSELECT created_at::date FROM t WHERE id = :id;")
    assert "created_at::date" in parse(path, "pkg")["a"].sql


# ── Migrations and Db (need Postgres) ────────────────────────────────────────

def test_migrations_create_lattice_schema_once(db):
    assert db.conn.exec_driver_sql(
        "SELECT count(*) FROM lattice.role").scalar() == 3
    assert migrate(sources_for([])) == []          # already applied in the template


def test_db_calls(db, tmp_path):
    sql = sql_queries(write(tmp_path, GOOD)).things
    assert db.one(sql.by_code, code="admin")["label"] == "Administrator"
    assert db.first(sql.by_code, code="nobody") is None
    with pytest.raises(NotFound, match="pkg/things.by_code"):
        db.one(sql.by_code, code="nobody")
    assert db.run(sql.add, code="auditor", label="Auditor") == 1
    assert db.value(sql.count) == 4
    assert [r["code"] for r in db.all(sql.codes_in, codes=["viewer", "auditor", "x"])] == \
        ["auditor", "viewer"]


def test_dicts_are_stored_as_jsonb(db, tmp_path):
    sql = sql_queries(write(tmp_path, GOOD)).things
    user_id = db.conn.exec_driver_sql(
        "INSERT INTO lattice.app_user (email, display_name) VALUES ('a@x', 'A') RETURNING id").scalar()
    db.run(sql.set_pref, user_id=user_id, key="grid", value={"hidden": ["a", "b"]})
    stored = db.conn.exec_driver_sql("SELECT value FROM lattice.user_preference").scalar()
    assert stored == {"hidden": ["a", "b"]}


def test_db_refuses_sql_text(db):
    with pytest.raises(TypeError, match="named queries"):
        db.all("SELECT 1")


def test_one_transaction_per_request(db, tmp_path):
    sql = sql_queries(write(tmp_path, GOOD)).things
    app = FastAPI()

    @app.post("/ok")
    def ok(d: Db = Depends(get_db)):
        d.run(sql.add, code="ok", label="Committed")
        return {}

    @app.post("/fails")
    def fails(d: Db = Depends(get_db)):
        d.run(sql.add, code="fails", label="Rolled back")
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.post("/ok").status_code == 200
        assert db.first(sql.by_code, code="ok") is not None      # committed before the response
        assert c.post("/fails").status_code == 500
    assert db.first(sql.by_code, code="fails") is None


def test_migration_runner_applies_new_files_in_order(db, tmp_path):
    folder = tmp_path / "schema"
    folder.mkdir()
    (folder / "0001_one.sql").write_text("CREATE TABLE extra.t (id int); INSERT INTO extra.t VALUES (1);")
    (folder / "0002_two.sql").write_text("INSERT INTO extra.t VALUES (2);")
    assert migrate([("extra", folder)]) == ["extra/0001_one.sql", "extra/0002_two.sql"]
    assert migrate([("extra", folder)]) == []
    assert db.conn.exec_driver_sql("SELECT count(*) FROM extra.t").scalar() == 2


def test_a_failing_migration_changes_nothing(db, tmp_path):
    folder = tmp_path / "schema"
    folder.mkdir()
    (folder / "0001_ok.sql").write_text("CREATE TABLE extra.t (id int);")
    (folder / "0002_bad.sql").write_text("INSERT INTO extra.missing VALUES (1);")
    with pytest.raises(Exception, match="missing"):
        migrate([("extra", folder)])
    assert db.conn.exec_driver_sql(
        "SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'extra'").scalar() == 0


def test_the_engine_is_shared():
    assert database.engine() is database.engine()
