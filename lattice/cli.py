"""The `lattice` command line.

    lattice migrate                      apply database migrations
    lattice new-migration SCHEMA "what"  create the next numbered migration file
    lattice reset                        drop, migrate and seed the development database
    lattice create-user EMAIL NAME [--role R]... [--no-password] [--keep-password]
    lattice seed                         development users, then each app's seed (not in production)
    lattice dev [--port 8000]            run the host with reload
    lattice docs build|check             regenerate (or check) the Reference pages

The host comes from LATTICE_HOST ("module:attribute", default showcase_host.main:app).
"""

from __future__ import annotations

import argparse
import getpass
import importlib

from lattice.kernel.auth import permissions
from lattice.kernel.auth.passwords import hash_password, policy_errors
from lattice.kernel.config import settings
from lattice.kernel.database import transaction
from lattice.kernel.dev_seed import DEV_USERS
from lattice.kernel.migrate import drop_list, drop_schemas, migrate_all, new_migration, sources_for
from lattice.kernel.queries import SQL
from lattice.kernel.services import users


def _load_host():
    module, _, attribute = settings.host.partition(":")
    return getattr(importlib.import_module(module), attribute)


def migrate(_args) -> None:
    host = _load_host()
    applied = migrate_all(host.state.apps)
    print("Applied: " + ", ".join(applied) if applied else "Nothing to apply.")
    with transaction() as db:
        new = permissions.sync(db)
    if new:
        print("New permissions: " + ", ".join(new))


def create_migration(args) -> None:
    folders = dict(sources_for(_load_host().state.apps))
    if args.schema not in folders:
        raise SystemExit(f"No schema {args.schema!r}. Schemas: {', '.join(folders)}")
    print(f"Created {new_migration(folders[args.schema], args.description)}")


def reset(_args) -> None:
    if settings.is_production:
        raise SystemExit("Refusing to reset a production database.")
    schemas = drop_list(_load_host().state.apps)
    drop_schemas(schemas)
    print("Dropped schemas: " + ", ".join(schema for schema, _ in schemas))
    migrate(_args)
    seed(_args)


def create_user(args) -> None:
    password = None if args.no_password else _prompt_password()
    with transaction() as db:
        unknown = set(args.role) - users.role_codes(db)
        if unknown:
            raise SystemExit(f"Unknown role(s): {', '.join(sorted(unknown))}. "
                             f"Known: {', '.join(sorted(users.role_codes(db)))}")
        user = users.by_email(db, args.email) or users.create(db, args.email, args.name)
        db.run(SQL.users.rename, id=user["id"], display_name=args.name)
        db.run(SQL.users.set_active, ids=[user["id"]], active=True)
        if password:
            db.run(SQL.users.set_password, id=user["id"], password_hash=hash_password(password),
                   must_change=not args.keep_password)
        db.run(SQL.users.add_roles, user_id=user["id"], roles=args.role)
        roles = users.by_id(db, user["id"])["roles"]
    print(f"Saved {user['email']} with roles: {', '.join(roles) or 'none'}")


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
    with transaction() as db:
        if db.value(SQL.users.any_exist):
            print("Users exist; skipping. `make reset` recreates the development database.")
            return
        for email, name, password, roles in DEV_USERS:
            users.create(db, email, name, password=password, roles=roles)
        for app in host.state.apps:
            if app.seed:
                app.seed(db)
    print(f"Seeded. Sign in as {DEV_USERS[0][0]} / {DEV_USERS[0][2]}")


def dev(args) -> None:
    import uvicorn
    uvicorn.run(settings.host, reload=True, port=args.port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lattice", description="The Lattice command line.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply database migrations").set_defaults(run=migrate)
    p = sub.add_parser("new-migration", help="create the next numbered migration file for a schema")
    p.add_argument("schema", help="lattice, or an app's key such as showcase")
    p.add_argument("description", help='what changes, e.g. "add ticket table"')
    p.set_defaults(run=create_migration)
    sub.add_parser("reset", help="drop and rebuild the development database, then seed it "
                                 "(refused in production)").set_defaults(run=reset)
    p = sub.add_parser("create-user", help="create or update a user (first admin)")
    p.add_argument("email", help="sign-in email; an existing user with it is updated")
    p.add_argument("name", help="display name")
    p.add_argument("--role", action="append", default=[], help="repeatable, e.g. --role admin")
    p.add_argument("--no-password", action="store_true", help="no password: the user signs in with SSO only")
    p.add_argument("--keep-password", action="store_true", help="do not force a change at sign-in")
    p.set_defaults(run=create_user)
    sub.add_parser("seed", help="development users and example data").set_defaults(run=seed)
    p = sub.add_parser("dev", help="run the host with reload")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(run=dev)
    p = sub.add_parser("docs", help="regenerate the Reference pages of the documentation")
    p.add_argument("action", choices=["build", "check"],
                   help="build writes the pages; check fails if they are out of date")
    p.set_defaults(run=docs)
    return parser


def docs(args) -> None:
    from lattice import reference
    parser = build_parser()
    stale = reference.write(parser) if args.action == "build" else reference.stale(parser)
    if args.action == "check" and stale:
        raise SystemExit(f"Out of date: {', '.join(stale)}. Run `lattice docs build`.")
    print("Written: " + ", ".join(stale) if stale else "Reference pages are up to date.")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
