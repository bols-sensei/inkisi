"""Separate self-service badges for event members."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0009_member_badges'
down_revision = '0008_uuid_badge_references'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {c['name'] for c in inspect(bind).get_columns('events')}
    if 'member_badge_token' not in columns:
        op.add_column('events', sa.Column('member_badge_token', sa.String(128), nullable=True))
    if 'member_badge_config' not in columns:
        op.add_column('events', sa.Column('member_badge_config', sa.Text(), nullable=False, server_default='{}'))
    indexes = {i['name'] for i in inspect(bind).get_indexes('events')}
    if 'ix_events_member_badge_token' not in indexes:
        op.create_index('ix_events_member_badge_token', 'events', ['member_badge_token'], unique=True)
    if 'member_badges' not in inspect(bind).get_table_names():
        op.create_table(
            'member_badges',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('event_id', sa.Integer(), sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False),
            sa.Column('full_name', sa.String(180), nullable=False),
            sa.Column('email', sa.String(254), nullable=False),
            sa.Column('organization_name', sa.String(180), nullable=False, server_default=''),
            sa.Column('category', sa.String(60), nullable=False),
            sa.Column('public_token', sa.String(128), nullable=False),
            sa.Column('badge_reference', sa.String(36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('event_id', 'email', name='uq_member_badge_event_email'),
            sa.UniqueConstraint('badge_reference', name='uq_member_badges_reference'),
            sa.UniqueConstraint('public_token', name='uq_member_badge_public_token'),
        )
        op.create_index('ix_member_badges_event_id', 'member_badges', ['event_id'])
        op.create_index('ix_member_badges_public_token', 'member_badges', ['public_token'], unique=True)


def downgrade():
    pass
