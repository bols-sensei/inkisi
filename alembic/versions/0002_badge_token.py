"""Separate participant badge credential from the personal management link."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
revision='0002_badge_token'
down_revision='0001_bootstrap'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind(); inspector=inspect(bind)
    if 'badge_token' not in {c['name'] for c in inspector.get_columns('conference_registrations')}:
        op.add_column('conference_registrations',sa.Column('badge_token',sa.String(128),nullable=True))
    indexes={i['name'] for i in inspect(bind).get_indexes('conference_registrations')}
    if 'uq_conference_registrations_badge_token' not in indexes:
        op.create_index('uq_conference_registrations_badge_token','conference_registrations',['badge_token'],unique=True)
    # Populate a unique credential for registrations created before this migration.
    rows=bind.execute(sa.text('SELECT id FROM conference_registrations WHERE badge_token IS NULL')).fetchall()
    import secrets
    for row in rows:
        bind.execute(sa.text('UPDATE conference_registrations SET badge_token=:token WHERE id=:id'),{'token':secrets.token_urlsafe(36),'id':row.id})

def downgrade():
    # Keep credentials intact; downgrade intentionally avoids destructive data loss.
    pass
