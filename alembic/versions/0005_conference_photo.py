"""Ajout du champ photo_data pour les badges de conférence personnalisés avec photo.

Idempotente : vérifie l'existence de la colonne avant de l'ajouter.
Compatible SQLite et PostgreSQL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0005_conference_photo'
down_revision = '0004_integrity_audit'
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
    _add(bind, 'conference_registrations', sa.Column('photo_data', sa.Text(), nullable=True))


def downgrade():
    pass
