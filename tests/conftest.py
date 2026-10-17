"""Test setup: a fresh SQLite database per test, built by the Alembic migrations."""

from __future__ import annotations

import os
import re

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test-unused.db")

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app import db as app_db
from app.auth import csrf as csrf_cookie
from app.models import Message, User, WorkItem
from app.services import users as users_service

PASSWORD = "Passw0rd-Long!"


@pytest.fixture
def db(tmp_path):
    app_db.configure(f"sqlite:///{tmp_path / 'test.db'}")
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
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
def items(db, users):
    rows = []
    for i, (status, owner) in enumerate([
        ("new", "editor"), ("in_review", "editor"), ("approved", "viewer"),
        ("declined", None), ("new", None), ("new", "admin"),
    ], start=1):
        rows.append(WorkItem(ref=f"WI-{i:05d}", title=f"Item {i} {'Marine' if i % 2 else 'Cyber'}",
                             account="Acme" if i < 4 else "Globex", status=status,
                             owner_id=users[owner].id if owner else None, amount=i * 1000))
    db.add_all(rows)
    for who in ("editor", "viewer"):
        db.add(Message(owner_id=users[who].id, sender_name="Bob", sender_email="b@x.io",
                       subject=f"Hello {who}", body="Hi"))
    db.commit()
    return rows


@pytest.fixture
def client(db):
    from app.main import app
    with TestClient(app) as c:
        yield c


def csrf(client) -> str:
    if csrf_cookie.COOKIE_NAME not in client.cookies:
        client.get("/auth/login")
    return client.cookies[csrf_cookie.COOKIE_NAME]


def login(client, email, password=PASSWORD):
    token = csrf(client)
    resp = client.post("/auth/login", data={"email": email, "password": password,
                                            "csrf_token": token, "next": "/"},
                       follow_redirects=False)
    return resp


@pytest.fixture
def as_user(client, users):
    def _as(role):
        client.cookies.clear()
        assert login(client, users[role].email).status_code == 303
        return client
    return _as


def post_json(client, url, body):
    return client.post(url, json=body, headers={"X-CSRF-Token": csrf(client)})


def current(user, roles=None):
    """A CurrentUser for calling grid code directly, without a request."""
    from app.auth.sessions import CurrentUser
    return CurrentUser(id=user.id, email=user.email, display_name=user.display_name,
                       roles=tuple(roles or user.role_codes), must_change_password=False,
                       has_password=True, session_id="test")


def extract(pattern, text):
    m = re.search(pattern, text)
    return m.group(1) if m else None
