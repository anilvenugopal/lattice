"""Platform tables: users, roles, sessions, preferences, audit. Apps define their own
tables in their own packages. Every schema change needs an Alembic revision (AGENTS.md).

Timestamps are naive UTC (`utcnow()`); templates convert for display.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lattice.kernel.db import Base


def utcnow() -> datetime:
    """The current time as naive UTC, the form every timestamp column stores."""
    return datetime.now(UTC).replace(tzinfo=None)


# ── Platform tables ──────────────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "role"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(255), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class User(Base):
    """A person who can sign in. Apps refer to users by `User.id`."""

    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    # NULL for OIDC-only accounts; verify_password() rejects NULL.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    oidc_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    roles: Mapped[list[UserRole]] = relationship(
        cascade="all, delete-orphan", lazy="selectin")

    @property
    def role_codes(self) -> list[str]:
        return sorted(r.role_code for r in self.roles)

    @property
    def sign_in_methods(self) -> str:
        methods = [label for present, label in ((self.password_hash, "Password"),
                                                 (self.oidc_subject, "Single sign-on")) if present]
        return " and ".join(methods) or "None"


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("role.code"), primary_key=True)


class UserSession(Base):
    __tablename__ = "user_session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    auth_method: Mapped[str] = mapped_column(String(16), default="password")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)


class UserPreference(Base):
    __tablename__ = "user_preference"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_type: Mapped[str] = mapped_column(String(64), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(String(512), default="")
    detail: Mapped[dict | None] = mapped_column(JSON)
