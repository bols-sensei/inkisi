"""SaaS : e-mail des comptes, révocation des sessions, jetons à usage unique, superadmin hors tenant.

Migration idempotente : sur une base neuve, 0001 (create_all) a déjà créé colonnes et table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0003_saas_accounts'
down_revision = '0002_badge_token'
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
    _add(bind, 'users', sa.Column('email', sa.String(254), nullable=True))
    _add(bind, 'users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
    _add(bind, 'users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))
    index_names = {i['name'] for i in inspect(bind).get_indexes('users')}
    if 'ix_users_email' not in index_names:
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if 'user_tokens' not in inspect(bind).get_table_names():
        op.create_table(
            'user_tokens',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('purpose', sa.String(20), nullable=False),
            sa.Column('token_hash', sa.String(128), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_user_tokens_user_id', 'user_tokens', ['user_id'])
        op.create_index('ix_user_tokens_token_hash', 'user_tokens', ['token_hash'], unique=True)

    # Comptes existants : adresse inconnue, donc considérés comme déjà validés (pas de blocage rétroactif).
    bind.execute(sa.text("UPDATE users SET email_verified = :t WHERE email IS NULL"), {'t': True})
    # Le personnel de la plateforme n'appartient à aucune organisation cliente.
    bind.execute(sa.text("UPDATE users SET organization_id = NULL WHERE role = 'superadmin'"))
    # L'essai n'est plus illimité (seulement si la formule d'essai n'a pas été ajustée à la main).
    bind.execute(sa.text("UPDATE plans SET event_limit = 2 WHERE code = 'trial' AND event_limit = -1"))


def downgrade():
    # Volontairement non destructif (cf. 0001) : restaurer une sauvegarde pour revenir en arrière.
    pass
