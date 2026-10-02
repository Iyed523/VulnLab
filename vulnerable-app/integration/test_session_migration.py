"""Round-trip the M8 migration only on the CI-owned disposable database."""

from alembic import command
from sqlalchemy import text

from vulnlab_vulnerable.seed import seed_demo

from .conftest import alembic_config


def test_m8_migration_preserves_existing_records(databases):
    database, migration = databases
    seed_demo(database)
    with migration.engine.begin() as connection:
        config = alembic_config(connection)
        command.downgrade(config, "0001_data_foundation")

        def records():
            users = connection.execute(
                text(
                    "SELECT id, username, password_hash, display_name, role, active, created_at, updated_at FROM users ORDER BY id"
                )
            ).all()
            return (
                users,
                connection.execute(text("SELECT * FROM tickets ORDER BY id")).all(),
                connection.execute(text("SELECT * FROM comments ORDER BY id")).all(),
            )

        before = records()
        command.upgrade(config, "head")
        assert records() == before
        assert connection.execute(
            text("SELECT session_version FROM users ORDER BY id")
        ).scalars().all() == [0, 0, 0]
        command.upgrade(config, "head")
        command.check(config)
