"""Display helpers shared by Python code and templates."""

from __future__ import annotations


def initials(name: str | None, fallback: str = "") -> str:
    """Up to two initials from a person's name, e.g. "Ada Lovelace" -> "AL"."""
    parts = (name or "").split()
    return "".join(p[0] for p in parts[:2]).upper() or fallback[:1].upper()
