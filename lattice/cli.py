"""The `lattice` command line.

    lattice migrate                      apply database migrations
    lattice create-user EMAIL NAME [--role R]... [--no-password] [--keep-password]
    lattice seed                         development users, then each app's seed (not in production)
    lattice dev [--port 8000]            run the host with reload

The host comes from LATTICE_HOST ("module:attribute", default demo_host.main:app).
"""

from __future__ import annotations

import argparse
import getpass
import importlib

from alembic.config import Config
from sqlalchemy import select

from alembic import command
from lattice.kernel.auth.passwords import hash_password, policy_errors
from lattice.kernel.config import settings
from lattice.kernel.db import SessionLocal
from lattice.kernel.dev_seed import DEV_USERS
from lattice.kernel.models import User, UserRole
from lattice.kernel.services import users


def _load_host():
    module, _, attribute = settings.host.partition(":")
    return getattr(importlib.import_module(module), attribute)


def migrate(_args) -> None:
    command.upgrade(Config("alembic.ini"), "head")


def create_user(args) -> None:
    password = None if args.no_password else _prompt_password()
    with SessionLocal() as db:
        unknown = set(args.role) - users.role_codes(db)
        if unknown:
            raise SystemExit(f"Unknown role(s): {', '.join(sorted(unknown))}. "
                             f"Known: {', '.join(sorted(users.role_codes(db)))}")
        user = users.by_email(db, args.email) or users.create(db, args.email, args.name)
        user.display_name = args.name
        user.is_active = True
        if password:
            user.password_hash = hash_password(password)
            user.must_change_password = not args.keep_password
        have = set(user.role_codes)
        user.roles += [UserRole(role_code=r) for r in dict.fromkeys(args.role) if r not in have]
        db.commit()
        print(f"Saved {user.email} with roles: {', '.join(user.role_codes) or 'none'}")


def _prompt_password() -> str:
    while True:
        pw = getpass.getpass("Password: ")
        if problems := policy_errors(pw):
            print("Password needs: " + "; ".join(problems))
        elif pw != getpass.getpass("Repeat: "):
            print("Passwords differ.")
        else:
            return pw


def seed(_args) -> None:
    if settings.is_production:
        raise SystemExit("Refusing to seed a production database.")
    host = _load_host()
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)):
            print("Users exist; skipping. `make reset` recreates the development database.")
            return
        for email, name, password, roles in DEV_USERS:
            users.create(db, email, name, password=password, roles=roles)
        db.commit()
        for app in host.state.apps:
            if app.seed:
                app.seed(db)
    print(f"Seeded. Sign in as {DEV_USERS[0][0]} / {DEV_USERS[0][2]}")


def dev(args) -> None:
    import uvicorn
    uvicorn.run(settings.host, reload=True, port=args.port)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lattice")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply database migrations").set_defaults(run=migrate)
    p = sub.add_parser("create-user", help="create or update a user (first admin)")
    p.add_argument("email")
    p.add_argument("name")
    p.add_argument("--role", action="append", default=[], help="repeatable, e.g. --role admin")
    p.add_argument("--no-password", action="store_true", help="SSO-only account")
    p.add_argument("--keep-password", action="store_true", help="do not force a change at sign-in")
    p.set_defaults(run=create_user)
    sub.add_parser("seed", help="development users and example data").set_defaults(run=seed)
    p = sub.add_parser("dev", help="run the host with reload")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(run=dev)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
