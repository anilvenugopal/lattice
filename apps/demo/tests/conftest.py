import pytest

import lattice_demo
from lattice_demo.models import Message, WorkItem


@pytest.fixture
def host_apps():
    return [lattice_demo.APP]


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
