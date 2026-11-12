"""Add stable UUID v4 references for invitations and conference badges."""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0008_uuid_badge_references'
down_revision = '0007_manual_guests'
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {column['name'] for column in inspect(bind).get_columns(table)}


def _add_column(bind, table):
    if 'badge_reference' in _columns(bind, table):
        return
    column = sa.Column('badge_reference', sa.String(36), nullable=True)
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)
    else:
        op.add_column(table, column)


def _set_not_null(bind, table):
    column = next(c for c in inspect(bind).get_columns(table) if c['name'] == 'badge_reference')
    if not column['nullable']:
        return
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(table) as batch:
            batch.alter_column('badge_reference', existing_type=sa.String(36), nullable=False)
    else:
        op.alter_column(table, 'badge_reference', existing_type=sa.String(36), nullable=False)


def _backfill(bind, table):
    rows = bind.execute(sa.text(f'SELECT id FROM {table} WHERE badge_reference IS NULL')).fetchall()
    for row in rows:
        bind.execute(sa.text(f'UPDATE {table} SET badge_reference=:reference WHERE id=:id'),
                     {'reference': str(uuid.uuid4()), 'id': row.id})


def _add_unique_index(bind, table, name):
    indexes = {index['name'] for index in inspect(bind).get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, ['badge_reference'], unique=True)


def upgrade():
    bind = op.get_bind()
    for table, index in (
        ('invitations', 'uq_invitations_badge_reference'),
        ('conference_registrations', 'uq_conference_registrations_badge_reference'),
    ):
        _add_column(bind, table)
        _backfill(bind, table)
        _set_not_null(bind, table)
        _add_unique_index(bind, table, index)


def downgrade():
    # Keep references stable if an operator rolls back application code.
    pass
