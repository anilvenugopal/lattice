from dataclasses import dataclass
from pathlib import Path

import pytest

import lattice_showcase
from lattice.api import sql_queries

CHECK = sql_queries(Path(__file__).parent / "sql").checks


@dataclass(frozen=True)
class Row:
    id: int


@pytest.fixture
def host_apps():
    return [lattice_showcase.APP]


@pytest.fixture
def items(db, users):
    rows = []
    for i, (status, owner) in enumerate([
        ("new", "editor"), ("active", "editor"), ("done", "viewer"),
        ("blocked", None), ("new", None), ("new", "admin"),
    ], start=1):
        rows.append(Row(db.value(
            CHECK.add_item, ref=f"IT-{i:04d}", name=f"Item {i} {'Alpha' if i % 2 else 'Beta'}",
            category="hardware" if i < 4 else "software", status=status,
            owner_id=users[owner].id if owner else None, amount=i * 1000)))
    for who in ("editor", "viewer"):
        db.value(CHECK.add_message, owner_id=users[who].id, sender_name="Bob",
                 sender_email="b@x.io", subject=f"Hello {who}", body="Hi")
    return rows
