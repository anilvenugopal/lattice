"""Password hashing and policy."""

from __future__ import annotations

from functools import cache

import bcrypt

from lattice.kernel.config import settings

MIN_LENGTH = 12


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


@cache
def _dummy_hash() -> str:
    return hash_password("timing-equaliser-not-a-password")


def verify_password(plain: str, hashed: str | None) -> bool:
    """False for accounts with no password hash, so OIDC-only users cannot sign in with one.

    Runs bcrypt even then, against a fixed hash, so timing does not reveal the account state.
    """
    if not hashed:
        bcrypt.checkpw(plain.encode(), _dummy_hash().encode())
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def policy_errors(plain: str) -> list[str]:
    errors = []
    if len(plain) < MIN_LENGTH:
        errors.append(f"At least {MIN_LENGTH} characters")
    if not any(c.isupper() for c in plain):
        errors.append("At least one uppercase letter")
    if not any(c.islower() for c in plain):
        errors.append("At least one lowercase letter")
    if not any(c.isdigit() for c in plain):
        errors.append("At least one digit")
    return errors
