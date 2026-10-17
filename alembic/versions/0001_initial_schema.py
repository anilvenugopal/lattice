"""initial schema: platform tables, built-in roles, example feature tables

Revision ID: 0001
Revises: 
Create Date: 2026-10-17 02:32:04.851238
"""
import sqlalchemy as sa

from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('app_user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('oidc_subject', sa.String(length=255), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('oidc_subject')
    )
    op.create_table('role',
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('label', sa.String(length=64), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    role = sa.table("role", sa.column("code", sa.String), sa.column("label", sa.String),
                    sa.column("description", sa.String), sa.column("sort_order", sa.Integer))
    op.bulk_insert(role, [
        {"code": "admin", "label": "Administrator", "sort_order": 1,
         "description": "Everything, plus Administration: users, roles, sessions, audit log."},
        {"code": "editor", "label": "Editor", "sort_order": 2,
         "description": "Create and change records; run bulk actions."},
        {"code": "viewer", "label": "Viewer", "sort_order": 3,
         "description": "Read access to every page outside Administration."},
    ])
    op.create_table('audit_event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('target_type', sa.String(length=64), nullable=False),
    sa.Column('target_id', sa.String(length=64), nullable=False),
    sa.Column('summary', sa.String(length=512), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['app_user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_event', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_event_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_event_at'), ['at'], unique=False)

    op.create_table('job',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('job_type', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('progress', sa.Integer(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('submitted_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.Column('error', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['submitted_by'], ['app_user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_job_status'), ['status'], unique=False)

    op.create_table('message',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('folder', sa.String(length=16), nullable=False),
    sa.Column('sender_name', sa.String(length=255), nullable=False),
    sa.Column('sender_email', sa.String(length=255), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('labels', sa.String(length=255), nullable=False),
    sa.Column('has_attachment', sa.Boolean(), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('is_starred', sa.Boolean(), nullable=False),
    sa.Column('received_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['app_user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_message_owner_id'), ['owner_id'], unique=False)

    op.create_table('user_preference',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'key')
    )
    op.create_table('user_role',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role_code', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['role_code'], ['role.code'], ),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_code')
    )
    op.create_table('user_session',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=False),
    sa.Column('user_agent', sa.String(length=512), nullable=False),
    sa.Column('auth_method', sa.String(length=16), nullable=False),
    sa.Column('revoked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user_session', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_session_user_id'), ['user_id'], unique=False)

    op.create_table('work_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ref', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('account', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('priority', sa.String(length=16), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('received_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['app_user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('ref')
    )
    with op.batch_alter_table('work_item', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_work_item_status'), ['status'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('work_item', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_work_item_status'))

    op.drop_table('work_item')
    with op.batch_alter_table('user_session', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_session_user_id'))

    op.drop_table('user_session')
    op.drop_table('user_role')
    op.drop_table('user_preference')
    with op.batch_alter_table('message', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_message_owner_id'))

    op.drop_table('message')
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_job_status'))

    op.drop_table('job')
    with op.batch_alter_table('audit_event', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_event_at'))
        batch_op.drop_index(batch_op.f('ix_audit_event_action'))

    op.drop_table('audit_event')
    op.drop_table('role')
    op.drop_table('app_user')
