"""Destructive tests require the dedicated CI disposable-database marker."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from vulnlab_vulnerable.database import Database, DatabaseConfig


@pytest.fixture(scope="session")
def databases():
    if os.environ.get("VULNLAB_EPHEMERAL_DB") != "ci-only":
        pytest.fail("Integration suite requires its explicitly disposable CI database")
    app = Database(DatabaseConfig.from_mapping(os.environ))
    values = dict(
        os.environ,
        DB_USER="vulnlab_migrate",
        DB_PASSWORD=os.environ["MIGRATION_DB_PASSWORD"],
    )
    migration = Database(DatabaseConfig.from_mapping(values))
    try:
        yield app, migration
    finally:
        app.dispose()
        migration.dispose()


def alembic_config(connection):
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_schema(databases):
    app, migration = databases
    with migration.engine.begin() as connection:
        config = alembic_config(connection)
        command.downgrade(config, "base")
        assert not connection.execute(
            text("SELECT to_regclass('public.users')")
        ).scalar()
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            == "0002_session_version"
        )


@pytest.fixture(autouse=True)
def clean_test_records(databases, migrated_schema):
    # These tables/database belong only to this disposable CI run.
    database, _ = databases

    def clean():
        with database.engine.begin() as connection:
            for table in ("comments", "tickets", "users"):
                connection.execute(text(f"DELETE FROM {table}"))

    clean()
    yield
    clean()
