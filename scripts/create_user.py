"""Create or update a user from the command line. Use this to create the first admin.

    uv run python -m scripts.create_user admin@corp.com "Ada Admin" --role admin
    uv run python -m scripts.create_user sso.user@corp.com "Sam SSO" --role viewer --no-password

Prompts for a password unless --no-password. The user must change it at first sign-in
unless --keep-password is given.
"""

from __future__ import annotations

import argparse
import getpass

from lattice.kernel.auth.passwords import hash_password, policy_errors
from lattice.kernel.db import SessionLocal
from lattice.kernel.models import UserRole
from lattice.kernel.services import users


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("email")
    p.add_argument("name")
    p.add_argument("--role", action="append", default=[], help="repeatable; e.g. --role admin")
    p.add_argument("--no-password", action="store_true", help="SSO-only account")
    p.add_argument("--keep-password", action="store_true", help="do not force a change at sign-in")
    args = p.parse_args()

    password = None if args.no_password else prompt_password()
    with SessionLocal() as db:
        unknown = set(args.role) - users.role_codes(db)
        if unknown:
            raise SystemExit(f"Unknown role(s): {', '.join(sorted(unknown))}. "
                             f"Known: {', '.join(sorted(users.role_codes(db)))}")
        user = users.by_email(db, args.email)
        if user is None:
            user = users.create(db, args.email, args.name)
        user.display_name = args.name
        user.is_active = True
        if password:
            user.password_hash = hash_password(password)
            user.must_change_password = not args.keep_password
        have = set(user.role_codes)
        user.roles += [UserRole(role_code=r) for r in dict.fromkeys(args.role) if r not in have]
        db.commit()
        print(f"Saved {user.email} with roles: {', '.join(user.role_codes) or 'none'}")


def prompt_password() -> str:
    while True:
        pw = getpass.getpass("Password: ")
        if problems := policy_errors(pw):
            print("Password needs: " + "; ".join(problems))
        elif pw != getpass.getpass("Repeat: "):
            print("Passwords differ.")
        else:
            return pw

if __name__ == "__main__":
    main()
