"""Lot 2 : idempotence par événement, date réelle des scans hors ligne, journal d'audit par organisation.

Idempotente : sur une base neuve, 0001 (create_all) a déjà créé le schéma courant.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0004_integrity_audit'
down_revision = '0003_saas_accounts'
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


def _replace_global_idempotency(bind, table, new_name):
    """Supprime l'unicité globale de idempotency_key et la remplace par (event_id, idempotency_key)."""
    insp = inspect(bind)
    ucs = [u for u in insp.get_unique_constraints(table) if u['column_names'] == ['idempotency_key']]
    idxs = [i for i in insp.get_indexes(table) if i.get('unique') and i['column_names'] == ['idempotency_key'] and not i.get('duplicates_constraint')]
    has_new = any(u['name'] == new_name for u in insp.get_unique_constraints(table))
    if not ucs and not idxs and has_new:
        return
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(table, recreate='always') as batch:
            for u in ucs:
                if u['name']: batch.drop_constraint(u['name'], type_='unique')
            for i in idxs:
                batch.drop_index(i['name'])
            if not has_new:
                batch.create_unique_constraint(new_name, ['event_id', 'idempotency_key'])
    else:
        for u in ucs:
            op.drop_constraint(u['name'], table, type_='unique')
        for i in idxs:
            op.drop_index(i['name'], table_name=table)
        if not has_new:
            op.create_unique_constraint(new_name, table, ['event_id', 'idempotency_key'])


def upgrade():
    bind = op.get_bind()
    _add(bind, 'entry_records', sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True))
    _add(bind, 'audit_logs', sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True))
    if 'ix_audit_logs_organization_id' not in {i['name'] for i in inspect(bind).get_indexes('audit_logs')}:
        op.create_index('ix_audit_logs_organization_id', 'audit_logs', ['organization_id'])
    # Rattrachage du journal existant : organisation de l'événement, sinon de l'auteur.
    bind.execute(sa.text("UPDATE audit_logs SET organization_id = (SELECT e.organization_id FROM events e WHERE e.id = audit_logs.event_id) "
                         "WHERE organization_id IS NULL AND event_id IS NOT NULL"))
    bind.execute(sa.text("UPDATE audit_logs SET organization_id = (SELECT u.organization_id FROM users u WHERE u.id = audit_logs.user_id) "
                         "WHERE organization_id IS NULL"))
    _replace_global_idempotency(bind, 'entry_records', 'uq_entry_event_idempotency')
    _replace_global_idempotency(bind, 'conference_checkins', 'uq_conference_event_idempotency')


def downgrade():
    # Volontairement non destructif (cf. 0001) : restaurer une sauvegarde pour revenir en arrière.
    pass
