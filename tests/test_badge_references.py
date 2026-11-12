import importlib.util
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_uuid_badge_reference_migration_backfills_existing_rows_and_is_repeatable():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0008_uuid_badge_references.py"
    spec = importlib.util.spec_from_file_location("migration_0008", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("invitations", "conference_registrations"):
            connection.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
            connection.execute(sa.text(f"INSERT INTO {table} (id) VALUES (1), (2)"))
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
            migration.upgrade()

        for table, index in (
            ("invitations", "uq_invitations_badge_reference"),
            ("conference_registrations", "uq_conference_registrations_badge_reference"),
        ):
            refs = [row[0] for row in connection.execute(sa.text(f"SELECT badge_reference FROM {table}"))]
            assert len(set(refs)) == 2
            assert all(UUID(value).version == 4 for value in refs)
            columns = {column["name"]: column for column in sa.inspect(connection).get_columns(table)}
            assert columns["badge_reference"]["nullable"] is False
            assert index in {item["name"] for item in sa.inspect(connection).get_indexes(table)}

