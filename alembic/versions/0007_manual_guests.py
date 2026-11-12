"""Ajout du champ is_manual pour distinguer l'origine des invités manuels.

Idempotente : vérifie l'existence des colonnes avant de les ajouter.
Compatible SQLite et PostgreSQL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0007_manual_guests'
down_revision = '0006_event_times_fields'
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
    _add(bind, 'conference_registrations', sa.Column('is_manual', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade():
    pass
