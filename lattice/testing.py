"""Pytest fixtures for Lattice and for apps built on it.

Enabled by `pytest_plugins = ["lattice.testing"]` in a conftest.py. Override the
`host_apps` fixture to run the tests against a host with your app:

    @pytest.fixture
    def host_apps():
        return [my_app.APP]
"""

from __future__ import annotations

import os

os.environ.setdefault("LATTICE_APP_ENV", "test")
os.environ.setdefault("LATTICE_BCRYPT_ROUNDS", "4")
# The Postgres server tests run against. Each test gets its own database on it.
TEST_SERVER_URL = os.environ.get("LATTICE_TEST_DATABASE_URL",
                                 "postgresql+psycopg://lattice:lattice@127.0.0.1:5436/lattice")
os.environ.setdefault("LATTICE_DATABASE_URL", TEST_SERVER_URL)

import hashlib  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, make_url  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from lattice.host import create_app  # noqa: E402
from lattice.kernel import database  # noqa: E402
from lattice.kernel.auth import csrf as csrf_cookie  # noqa: E402
from lattice.kernel.auth import permissions  # noqa: E402
from lattice.kernel.auth.sessions import CurrentUser  # noqa: E402
from lattice.kernel.database import Db, transaction  # noqa: E402
from lattice.kernel.migrate import libraries_for, migrate_all, sources_for  # noqa: E402
from lattice.kernel.services import users as users_service  # noqa: E402

PASSWORD = "Passw0rd-Long!"


def _url(name: str) -> str:
    return make_url(TEST_SERVER_URL).set(database=name).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def _pg_server():
    """A connection to the test server for creating and dropping databases."""
    server = create_engine(TEST_SERVER_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    templates: dict[tuple, str] = {}
    yield server, templates
    with server.connect() as conn:
        for name in templates.values():
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    server.dispose()


def _template(server, templates, apps) -> str:
    """A database migrated once per test run for these apps; tests copy it."""
    sources = sources_for(apps)
    key = (tuple((schema, str(folder)) for schema, folder in sources),
           tuple(library.name for library in libraries_for(apps)),
           tuple(sorted((p.key, p.default_roles) for a in apps for p in a.permissions)))
    if key not in templates:
        create_app(apps=apps)              # fills the permission catalogue to sync
        digest = hashlib.sha1(repr(key).encode()).hexdigest()[:10]
        name = f"lattice_test_template_{digest}"
        with server.connect() as conn:
            conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
        database.configure(_url(name))
        migrate_all(apps)
        with transaction() as db:          # grants as `lattice migrate` makes them
            permissions.sync(db)
        database.engine().dispose()      # a template must have no open connections
        templates[key] = name
    return templates[key]


@pytest.fixture
def db(_pg_server, host_apps):
    """A fresh Postgres database per test, already migrated, and a `Db` on it.

    Every call commits at once, so rows a test adds are visible to the test client.
    """
    server, templates = _pg_server
    template = _template(server, templates, host_apps)
    name = f"lattice_test_{uuid4().hex[:12]}"
    with server.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}" TEMPLATE "{template}"')
    database.configure(_url(name))
    conn = database.engine().connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        yield Db(conn)
    finally:
        conn.close()
        database.engine().dispose()
        with server.connect() as admin:
            admin.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@dataclass(frozen=True)
class TestUser:
    """A user made for a test: `users["editor"].id`."""

    id: int
    email: str
    display_name: str
    roles: tuple[str, ...]


def make_user(db, email, roles=("viewer",), password=PASSWORD, **kw) -> TestUser:
    user = users_service.create(db, email, email.split("@")[0].title(), password=password,
                                roles=roles, **kw)
    return TestUser(user["id"], user["email"], user["display_name"], tuple(user["roles"]))


@pytest.fixture
def users(db):
    return {
        "admin": make_user(db, "admin@test.io", ("admin",)),
        "editor": make_user(db, "editor@test.io", ("editor",)),
        "viewer": make_user(db, "viewer@test.io", ("viewer",)),
    }


@pytest.fixture
def host_apps():
    """The apps the test host runs. Core tests use none; an app's tests override this."""
    return []


@pytest.fixture
def client(db, host_apps):
    with TestClient(create_app(apps=host_apps)) as c:
        yield c


@pytest.fixture
def as_user(client, users):
    def _as(role):
        client.cookies.clear()
        assert login(client, users[role].email).status_code == 303
        return client
    return _as


def csrf(client) -> str:
    if csrf_cookie.COOKIE_NAME not in client.cookies:
        client.get("/auth/login")
    return client.cookies[csrf_cookie.COOKIE_NAME]


def login(client, email, password=PASSWORD):
    return client.post("/auth/login", data={"email": email, "password": password,
                                            "csrf_token": csrf(client), "next": "/"},
                       follow_redirects=False)


def post_json(client, url, body):
    return client.post(url, json=body, headers={"X-CSRF-Token": csrf(client)})


def current(user, roles=None, permissions=()) -> CurrentUser:
    """A CurrentUser for calling grid code directly, without a request."""
    return CurrentUser(id=user.id, email=user.email, display_name=user.display_name,
                       roles=tuple(roles or user.roles), must_change_password=False,
                       has_password=True, session_id="test", permissions=frozenset(permissions))
