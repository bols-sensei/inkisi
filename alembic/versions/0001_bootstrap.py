"""Bootstrap MVP schema and add reception management modules.

This migration is intentionally safe for an existing, unversioned MVP database:
create_all creates missing tables, then missing columns are added without dropping data.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from app.database import Base
from app import models  # register every model

revision = '0001_bootstrap'
down_revision = None
branch_labels = None
depends_on = None

def _add_missing(table, name, column):
    bind=op.get_bind(); inspector=inspect(bind)
    if table in inspector.get_table_names() and name not in {c['name'] for c in inspector.get_columns(table)}:
        if bind.dialect.name == 'sqlite':
            with op.batch_alter_table(table) as batch:
                batch.add_column(column)
        else:
            op.add_column(table,column)

def upgrade():
    bind=op.get_bind()
    # Create missing tables (including new modules); existing tables are not altered by create_all.
    Base.metadata.create_all(bind=bind, checkfirst=True)
    # Additive compatibility for pre-Phase-1 and Phase-1 databases.
    _add_missing('users','organization_id',sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id', name='fk_users_organization_id')))
    _add_missing('events','organization_id',sa.Column('organization_id',sa.Integer(),sa.ForeignKey('organizations.id', name='fk_events_organization_id')))
    _add_missing('events','event_type',sa.Column('event_type',sa.String(20),nullable=False,server_default='wedding'))
    _add_missing('events','capacity',sa.Column('capacity',sa.Integer(),nullable=True))
    _add_missing('events','registration_open',sa.Column('registration_open',sa.Boolean(),nullable=False,server_default=sa.false()))
    _add_missing('events','registration_token',sa.Column('registration_token',sa.String(128),nullable=True))
    _add_missing('entry_records','idempotency_key',sa.Column('idempotency_key',sa.String(100),nullable=True))
    _add_missing('conference_registrations','badge_token',sa.Column('badge_token',sa.String(128),nullable=True))
    inspector=inspect(bind)
    for table,col in [('users','organization_id'),('events','organization_id')]:
        index_name=f'ix_{table}_{col}'
        if table in inspector.get_table_names() and index_name not in {i['name'] for i in inspect(bind).get_indexes(table)}:
            op.create_index(index_name,table,[col],unique=False)
    # Tokens and sync ids must remain unique even for adopted legacy databases.
    indexes={i['name'] for i in inspect(bind).get_indexes('events')}
    if 'uq_events_registration_token' not in indexes:
        op.create_index('uq_events_registration_token','events',['registration_token'],unique=True)
    indexes={i['name'] for i in inspect(bind).get_indexes('conference_registrations')}
    if 'uq_conference_registrations_badge_token' not in indexes:
        op.create_index('uq_conference_registrations_badge_token','conference_registrations',['badge_token'],unique=True)
    indexes={i['name'] for i in inspect(bind).get_indexes('entry_records')}
    if 'uq_entry_records_idempotency_key' not in indexes:
        op.create_index('uq_entry_records_idempotency_key','entry_records',['idempotency_key'],unique=True)

def downgrade():
    # Deliberately non-destructive: this baseline may have adopted a production MVP database.
    # Use a forward migration for schema changes; never drop users/events/check-in records here.
    pass
