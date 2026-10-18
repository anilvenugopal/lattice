"""The `lattice` command line: seed and create-user."""

from pathlib import Path

import pytest

from lattice import cli
from lattice.components.manifest import AppManifest
from lattice.host import create_app
from lattice.kernel.config import settings
from lattice.kernel.dev_seed import DEV_USERS
from lattice.kernel.services import users as users_service
from lattice.kernel.sql import sql_queries

CHECK = sql_queries(Path(__file__).parent / "sql").checks


def test_seed_creates_dev_users_then_runs_each_app_seed(db, monkeypatch, capsys):
    seeded = []
    host = create_app(apps=[AppManifest(key="notes", label="Notes",
                                        seed=lambda session: seeded.append(session))])
    monkeypatch.setattr(cli, "_load_host", lambda: host)
    cli.main(["seed"])
    emails = {r["email"] for r in db.all(CHECK.user_emails)}
    assert {u[0] for u in DEV_USERS} <= emails and len(seeded) == 1
    cli.main(["seed"])                                   # users exist: nothing more happens
    assert len(seeded) == 1 and "skipping" in capsys.readouterr().out


def test_seed_refuses_production(db, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(SystemExit, match="production"):
        cli.main(["seed"])


def test_create_user_sets_password_and_roles(db, monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "Strong-Pass-123")
    cli.main(["create-user", "Ada@Corp.io", "Ada Admin", "--role", "admin"])
    user = users_service.by_email(db, "ada@corp.io")
    assert user["roles"] == ["admin"] and user["must_change_password"] and user["password_hash"]
    with pytest.raises(SystemExit, match="Unknown role"):
        cli.main(["create-user", "x@corp.io", "X", "--role", "root", "--no-password"])
