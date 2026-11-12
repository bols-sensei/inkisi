"""Member badge photos and organization support inbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0010_member_photo_support'
down_revision = '0009_member_badges'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'photo_data' not in {c['name'] for c in inspector.get_columns('member_badges')}:
        op.add_column('member_badges', sa.Column('photo_data', sa.Text(), nullable=True))
    tables = set(inspector.get_table_names())
    if 'support_tickets' not in tables:
        op.create_table('support_tickets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('subject', sa.String(180), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='open'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
        op.create_index('ix_support_tickets_organization_id', 'support_tickets', ['organization_id'])
        op.create_index('ix_support_tickets_status', 'support_tickets', ['status'])
        op.create_index('ix_support_tickets_updated_at', 'support_tickets', ['updated_at'])
    if 'support_messages' not in tables:
        op.create_table('support_messages',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('ticket_id', sa.Integer(), sa.ForeignKey('support_tickets.id', ondelete='CASCADE'), nullable=False),
            sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
        op.create_index('ix_support_messages_ticket_id', 'support_messages', ['ticket_id'])


def downgrade():
    pass
