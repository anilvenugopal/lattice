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
os.environ.setdefault("LATTICE_DATABASE_URL", "sqlite:///./data/test-unused.db")

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from alembic import command  # noqa: E402
from lattice.host import create_app  # noqa: E402
from lattice.kernel import db as app_db  # noqa: E402
from lattice.kernel.auth import csrf as csrf_cookie  # noqa: E402
from lattice.kernel.auth.sessions import CurrentUser  # noqa: E402
from lattice.kernel.models import User  # noqa: E402
from lattice.kernel.services import users as users_service  # noqa: E402

PASSWORD = "Passw0rd-Long!"


@pytest.fixture
def db(tmp_path):
    """A fresh database per test, built by the Alembic migrations."""
    app_db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    command.upgrade(Config("alembic.ini"), "head")
    with app_db.SessionLocal() as session:
        yield session


def make_user(db, email, roles=("viewer",), password=PASSWORD, **kw) -> User:
    user = users_service.create(db, email, email.split("@")[0].title(), password=password,
                                roles=roles, **kw)
    db.commit()
    return user


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


def current(user, roles=None) -> CurrentUser:
    """A CurrentUser for calling grid code directly, without a request."""
    return CurrentUser(id=user.id, email=user.email, display_name=user.display_name,
                       roles=tuple(roles or user.role_codes), must_change_password=False,
                       has_password=True, session_id="test")
