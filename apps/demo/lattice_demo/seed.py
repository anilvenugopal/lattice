"""Demo data: example work items, jobs and messages for the development users.

`seed(db)` is the app's AppManifest.seed, run by `lattice seed` after the
development users exist.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from lattice.api import Db, sql_queries
from lattice_demo import inbox, jobs, work_items

SQL = sql_queries(Path(__file__).parent / "sql").seed


def keys(options) -> list[str]:
    return [value for value, _ in options]


ACCOUNTS = ["Northwind Mutual", "Contoso Re", "Fabrikam Marine", "Tailspin Aviation", "Wingtip Energy",
            "Adventure Works", "Litware Holdings", "Proseware Logistics", "Alpine Ski House",
            "Coho Vineyard", "Fourth Coffee", "Margie's Travel", "Blue Yonder Airlines"]
SUBJECTS = ["Renewal", "New business", "Mid-term change", "Endorsement", "Quote request",
            "Claims review", "Referral", "Policy amendment"]
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


def seed_examples(db: Db, people: list[int]) -> None:
    rng = random.Random(7)
    now = datetime.now(UTC).replace(tzinfo=None)
    for i in range(1, 241):
        received = now - timedelta(hours=rng.randint(1, 24 * 90))
        db.run(SQL.add_work_item,
               ref=f"WI-{i:05d}", title=f"{rng.choice(SUBJECTS)} – {rng.choice(['Property', 'Casualty', 'Marine', 'Cyber', 'Aviation'])}",
               account=rng.choice(ACCOUNTS),
               status=rng.choices(keys(work_items.STATUSES), [3, 4, 4, 1])[0],
               priority=rng.choices(keys(work_items.PRIORITIES), [2, 5, 2, 1])[0],
               owner_id=rng.choice([None, *people]),
               amount=round(rng.uniform(5_000, 2_500_000), -2),
               description="Submitted by broker. Review the schedule of values and loss history before quoting.",
               received_at=received,
               updated_at=min(now, received + timedelta(hours=rng.randint(0, 48))))
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


def seed(db: Db) -> None:
    """Example rows owned by the users that exist (the development users)."""
    seed_examples(db, [r["id"] for r in db.all(SQL.people)])
