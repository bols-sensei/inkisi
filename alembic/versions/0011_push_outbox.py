"""Queue Web Push deliveries outside the request transaction."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0011_push_outbox'
down_revision = '0010_member_photo_support'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if 'push_outbox' not in tables:
        op.create_table(
            'push_outbox',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('notification_id', sa.Integer(), sa.ForeignKey('notifications.id', ondelete='CASCADE'), nullable=False),
            sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('push_subscriptions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
            sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_error', sa.String(40), nullable=False, server_default=''),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        inspector = inspect(bind)
    indexes = {index['name'] for index in inspector.get_indexes('push_outbox')}
    for name, columns in (
        ('ix_push_outbox_notification_id', ['notification_id']),
        ('ix_push_outbox_subscription_id', ['subscription_id']),
        ('ix_push_outbox_available_at', ['available_at']),
        ('ix_push_outbox_status_available_at', ['status', 'available_at']),
    ):
        if name not in indexes:
            op.create_index(name, 'push_outbox', columns)


def downgrade():
    bind = op.get_bind()
    if 'push_outbox' not in set(inspect(bind).get_table_names()):
        return
    for name in (
        'ix_push_outbox_status_available_at',
        'ix_push_outbox_available_at',
        'ix_push_outbox_subscription_id',
        'ix_push_outbox_notification_id',
    ):
        if name in {index['name'] for index in inspect(bind).get_indexes('push_outbox')}:
            op.drop_index(name, table_name='push_outbox')
    op.drop_table('push_outbox')
