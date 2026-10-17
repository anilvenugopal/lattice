"""Demo data: example work items, jobs and messages for the development users.

`seed(db)` is the app's AppManifest.seed. Run on its own with:

    uv run python -m lattice_demo.seed           # skips if users already exist
    uv run python -m lattice_demo.seed --reset   # deletes example rows first

Never run against production.
"""

from __future__ import annotations

import argparse
import random
from datetime import timedelta

from sqlalchemy import delete, select

from lattice.api import (
    DEV_USERS,
    SessionLocal,
    User,
    settings,
    users,
    utcnow,
)
from lattice_demo import inbox, jobs, work_items
from lattice_demo.models import Job, Message, WorkItem


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


def seed_users(db) -> list[User]:
    return [users.create(db, email, name, password=password, roles=roles)
            for email, name, password, roles in DEV_USERS]


def seed_examples(db, people: list[User]) -> None:
    rng = random.Random(7)
    now = utcnow()
    for i in range(1, 241):
        received = now - timedelta(hours=rng.randint(1, 24 * 90))
        db.add(WorkItem(
            ref=f"WI-{i:05d}", title=f"{rng.choice(SUBJECTS)} – {rng.choice(['Property', 'Casualty', 'Marine', 'Cyber', 'Aviation'])}",
            account=rng.choice(ACCOUNTS),
            status=rng.choices(keys(work_items.STATUSES), [3, 4, 4, 1])[0],
            priority=rng.choices(keys(work_items.PRIORITIES), [2, 5, 2, 1])[0],
            owner_id=rng.choice([None, *[u.id for u in people]]),
            amount=round(rng.uniform(5_000, 2_500_000), -2),
            description="Submitted by broker. Review the schedule of values and loss history before quoting.",
            received_at=received, updated_at=min(now, received + timedelta(hours=rng.randint(0, 48))),
        ))
    for _ in range(80):
        created = now - timedelta(minutes=rng.randint(5, 60 * 24 * 14))
        name, kind = rng.choice(JOBS)
        # jobs.STATUSES order: queued, running, succeeded, failed, cancelled
        status = rng.choices(keys(jobs.STATUSES), [1, 1, 12, 3, 1])[0]
        started = created + timedelta(seconds=rng.randint(1, 120))
        db.add(Job(
            name=name, job_type=kind, status=status, submitted_by=rng.choice(people).id,
            created_at=created, attempts=rng.choice([1, 1, 1, 2]),
            started_at=None if status == "queued" else started,
            finished_at=started + timedelta(seconds=rng.randint(20, 1800))
            if status in ("succeeded", "failed", "cancelled") else None,
            progress={"succeeded": 100, "queued": 0}.get(status, rng.randint(10, 90)),
            error="ConnectionError: upstream returned 503 Service Unavailable after 3 retries"
            if status == "failed" else "",
        ))
    for user in people:
        for i in range(60):
            sender, addr = rng.choice(SENDERS)
            db.add(Message(
                owner_id=user.id, folder="archive" if i % 7 == 0 else "inbox",
                sender_name=sender, sender_email=addr, subject=rng.choice(MAIL_SUBJECTS),
                body=BODY.format(name=sender.split()[0]),
                labels=rng.choice(["", "", *keys(inbox.LABELS)]),
                has_attachment=rng.random() < 0.3, is_read=rng.random() < 0.55,
                is_starred=rng.random() < 0.12,
                received_at=now - timedelta(minutes=rng.randint(1, 60 * 24 * 30)),
            ))


def seed(db) -> None:
    """Example rows owned by the users that exist (the development users)."""
    seed_examples(db, list(db.scalars(select(User).order_by(User.id))))
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="delete example rows and users first")
    args = parser.parse_args()
    if settings.is_production:
        raise SystemExit("Refusing to seed a production database.")
    with SessionLocal() as db:
        if args.reset:
            for model in (Message, Job, WorkItem):
                db.execute(delete(model))
            db.execute(delete(User).where(User.email.in_([u[0] for u in DEV_USERS])))
            db.commit()
        if db.scalar(select(User).limit(1)):
            print("Users exist; skipping. Use --reset to recreate the example data.")
            return
        seed_users(db)
        seed(db)
    print(f"Seeded. Sign in as {DEV_USERS[0][0]} / {DEV_USERS[0][2]}")


if __name__ == "__main__":
    main()
