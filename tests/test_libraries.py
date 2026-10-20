"""Libraries that migrate themselves (AppManifest.libraries): Taskline brings its migrate()."""

from pathlib import Path

import pytest

from lattice.api import AppManifest, Library, sql_queries
from lattice.kernel import database
from lattice.kernel.migrate import MigrationError, drop_list, libraries_for, migrate, migrate_all

CHECK = sql_queries(Path(__file__).parent / "sql").checks
CALLS: list[object] = []


def migrate_libtest(engine):
    """A library's own runner; here it reuses Lattice's for a folder of SQL."""
    CALLS.append(engine)
    return migrate([("libtest", Path(__file__).parent / "fixtures" / "libtest")])


LIBTEST = Library("libtest", ["libtest"], migrate_libtest)


@pytest.fixture
def host_apps():
    return [AppManifest(key="a", label="A", libraries=[LIBTEST]),
            AppManifest(key="b", label="B", libraries=[LIBTEST])]


def test_a_library_migrates_once_on_lattices_engine(db, host_apps):
    assert db.value(CHECK.schema_exists, name="libtest") == 1
    CALLS.clear()
    assert migrate_all(host_apps) == []                 # nothing pending the second time
    assert len(CALLS) == 1 and CALLS[0] is database.engine()


def test_libraries_are_listed_once_and_dropped_on_reset(host_apps):
    assert libraries_for(host_apps) == [LIBTEST]
    geo = ("geo", Path("/libs/geo"))
    app = AppManifest(key="c", label="C", library_schemas=[geo], libraries=[LIBTEST],
                      sql=Path("/apps/c/sql"))
    assert [s for s, _ in drop_list([app])] == ["lattice", "libtest", "geo", "c"]


def test_a_failing_library_is_named(db):
    def broken(engine):
        raise ValueError("the database role 'reader' does not exist")
    app = AppManifest(key="x", label="X", libraries=[Library("taskline", ["jobs"], broken)])
    with pytest.raises(MigrationError, match="Library 'taskline' failed to migrate: the database role"):
        migrate_all([app])
