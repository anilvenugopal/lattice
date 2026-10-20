"""Sample data: items, their dependencies, jobs, messages and documents.

`seed(db)` is the app's AppManifest.seed, run by `lattice seed` after the
development users exist.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lattice.api import Db, documents, sql_queries
from lattice_showcase import cat_seed, inbox, items, jobs, specs

SQL = sql_queries(Path(__file__).parent / "sql").seed


def keys(options) -> list[str]:
    return [value for value, _ in options]


NOUNS = ["Sensor array", "Billing service", "Onboarding flow", "Data pipeline", "Field survey",
         "Brand refresh", "Cooling unit", "Search index", "Supplier audit", "Mobile app",
         "Training plan", "Access review", "Prototype board", "Pricing model", "Help centre"]
QUALIFIERS = ["v2", "rollout", "upgrade", "pilot", "review", "migration", "redesign",
              "phase 1", "phase 2", "cleanup"]
TAGS = ["alpha", "beta", "external", "quick win", "needs review", "blocked upstream", "q4"]
COUNTRIES = ["United States of America", "United Kingdom", "Germany", "France", "India",
             "Japan", "Brazil", "Canada", "Australia", "South Africa", "Mexico", "Spain",
             "Italy", "Netherlands", "Sweden", "Singapore", "Kenya", "Argentina"]
NOTES = ["Waiting on the vendor's revised quote.", "Agreed scope in Tuesday's review.",
         "Second pass needed after the data refresh.", "", "", "Owner on leave until Friday."]
JOBS = [("Nightly sync: accounts", "sync"), ("Import submissions batch", "import"),
        ("Export monthly report", "export"), ("Rebuild search index", "cleanup"),
        ("Quarterly summary", "report"), ("Archive closed items", "cleanup")]
SENDERS = [("Morgan Lee", "morgan.lee@northwind.example"), ("Chris Park", "chris@contoso.example"),
           ("Dana Wu", "dana.wu@fabrikam.example"), ("Operations", "ops@example.com"),
           ("Finance Team", "finance@example.com"), ("Jordan Blake", "jordan@tailspin.example")]
MAIL_SUBJECTS = ["Updated schedule attached", "Question about the renewal terms", "Weekly operations summary",
                 "Invoice 4471 overdue", "Can we move Thursday's call?", "Loss runs for 2023–2025",
                 "Re: broker commission split", "Action needed: missing signature", "New submission received",
                 "Re: data quality issue in import"]
BODY = ("Hi,\n\nFollowing up on our conversation earlier this week. I have attached the latest figures "
        "and marked the open questions inline. Could you review them before Friday?\n\n"
        "The main change is the revised limit on the property schedule; the rest is unchanged from the "
        "previous version.\n\nThanks,\n{name}")


def seed_items(db: Db, people: list[int], rng: random.Random, now: datetime) -> None:
    """400 items over the last year; some have parents; items 1–20 depend on each other."""
    for i in range(1, 401):
        created = now - timedelta(hours=rng.randint(1, 24 * 365))
        status = rng.choices(keys(items.STATUSES), [3, 5, 1, 4, 1])[0]
        parent = rng.randint(1, 40) if i > 40 and rng.random() < 0.3 else None
        if parent is None and i > 120 and rng.random() < 0.1:
            parent = rng.randint(41, 120)          # a third level under some children
        db.run(SQL.add_item,
               id=i, ref=f"IT-{i:04d}",
               name=f"{rng.choice(NOUNS)} {rng.choice(QUALIFIERS)}",
               category=rng.choice(keys(items.CATEGORIES)), status=status,
               priority=rng.choices(keys(items.PRIORITIES), [2, 5, 2, 1])[0],
               owner_id=rng.choice([None, *people]), parent_id=parent,
               amount=round(rng.uniform(500, 250_000), 2),
               progress={"new": 0, "done": 100, "archived": 100}.get(status, rng.randint(5, 95)),
               score=round(rng.uniform(20, 99), 1),
               tags=",".join(rng.sample(TAGS, rng.choice([0, 1, 1, 2, 3]))),
               starred=rng.random() < 0.1, country=rng.choice(COUNTRIES),
               notes=rng.choice(NOTES),
               due_on=(created + timedelta(days=rng.randint(7, 120))).date()
               if rng.random() < 0.8 else None,
               created_at=created,
               updated_at=min(now, created + timedelta(hours=rng.randint(0, 24 * 30))))
    db.value(SQL.sync_item_ids)
    for to_id in range(2, 21):
        for from_id in rng.sample(range(1, to_id), min(to_id - 1, rng.choice([1, 1, 2]))):
            db.run(SQL.add_link, from_id=from_id, to_id=to_id)


def seed_documents(db: Db, user) -> None:
    for spec in [
        {"name": "Sensor array housing", "stage": "approved", "version": 3,
         "released_on": "2026-06-01", "tags": ["outdoor", "ip67"],
         "dimensions": [{"name": "Width", "value": 120, "unit": "mm"},
                        {"name": "Weight", "value": 0.8, "unit": "kg"}],
         "source": {"kind": "supplier", "name": "Fabrikam Plastics",
                    "email": "orders@fabrikam.example"}},
        {"name": "Billing service API", "stage": "review", "version": 1,
         "summary": "Public endpoints for invoices and credit notes.",
         "source": {"kind": "internal", "team": "Payments", "cost_centre": "CC-2041"},
         "legacy_ref": "BILL-77"},
    ]:
        documents.create(db, user, specs.SPEC, spec)


def seed_examples(db: Db, people: list[int]) -> None:
    rng = random.Random(7)
    now = datetime.now(UTC).replace(tzinfo=None)
    seed_items(db, people, rng, now)
    for _ in range(80):
        created = now - timedelta(minutes=rng.randint(5, 60 * 24 * 14))
        name, kind = rng.choice(JOBS)
        # jobs.STATUSES order: queued, running, succeeded, failed, cancelled
        status = rng.choices(keys(jobs.STATUSES), [1, 1, 12, 3, 1])[0]
        started = created + timedelta(seconds=rng.randint(1, 120))
        db.run(SQL.add_job,
               name=name, job_type=kind, status=status, submitted_by=rng.choice(people),
               created_at=created, attempts=rng.choice([1, 1, 1, 2]),
               started_at=None if status == "queued" else started,
               finished_at=started + timedelta(seconds=rng.randint(20, 1800))
               if status in ("succeeded", "failed", "cancelled") else None,
               progress={"succeeded": 100, "queued": 0}.get(status, rng.randint(10, 90)),
               error="ConnectionError: upstream returned 503 Service Unavailable after 3 retries"
               if status == "failed" else "")
    for user_id in people:
        for i in range(60):
            sender, addr = rng.choice(SENDERS)
            db.run(SQL.add_message,
                   owner_id=user_id, folder="archive" if i % 7 == 0 else "inbox",
                   sender_name=sender, sender_email=addr, subject=rng.choice(MAIL_SUBJECTS),
                   body=BODY.format(name=sender.split()[0]),
                   labels=rng.choice(["", "", *keys(inbox.LABELS)]),
                   has_attachment=rng.random() < 0.3, is_read=rng.random() < 0.55,
                   is_starred=rng.random() < 0.12,
                   received_at=now - timedelta(minutes=rng.randint(1, 60 * 24 * 30)))


class _Seeder:
    def __init__(self, user_id: int):
        self.id = user_id


def seed(db: Db) -> None:
    """Sample rows owned by the users that exist (the development users)."""
    people = [r["id"] for r in db.all(SQL.people)]
    seed_examples(db, people)
    seed_documents(db, _Seeder(people[0]))
    cat_seed.seed(db)
