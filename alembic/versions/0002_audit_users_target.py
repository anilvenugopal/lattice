"""audit: events about people use target_type "users"

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE audit_event SET target_type = 'users' WHERE target_type = 'user'")


def downgrade() -> None:
    pass  # "user" and "users" rows cannot be told apart afterwards
