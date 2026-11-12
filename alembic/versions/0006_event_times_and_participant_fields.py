"""Ajout des champs temporels sur les événements et des champs d'identité détaillés sur les inscriptions de conférence.

Idempotente : vérifie l'existence des colonnes avant de les ajouter.
Compatible SQLite et PostgreSQL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0006_event_times_fields'
down_revision = '0005_conference_photo'
branch_labels = None
depends_on = None


def _cols(bind, table):
    return {c['name'] for c in inspect(bind).get_columns(table)}


def _add(bind, table, column):
    if column.name in _cols(bind, table):
        return
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)
    else:
        op.add_column(table, column)


def upgrade():
    bind = op.get_bind()
    # Champs temporels d'événements
    _add(bind, 'events', sa.Column('start_date', sa.String(20), server_default='', nullable=False))
    _add(bind, 'events', sa.Column('start_time', sa.String(10), server_default='', nullable=False))
    _add(bind, 'events', sa.Column('end_date', sa.String(20), server_default='', nullable=False))
    _add(bind, 'events', sa.Column('end_time', sa.String(10), server_default='', nullable=False))

    # Identité participant conférence
    _add(bind, 'conference_registrations', sa.Column('first_name', sa.String(100), server_default='', nullable=False))
    _add(bind, 'conference_registrations', sa.Column('last_name', sa.String(100), server_default='', nullable=False))
    _add(bind, 'conference_registrations', sa.Column('profession', sa.String(180), server_default='', nullable=False))


def downgrade():
    pass
