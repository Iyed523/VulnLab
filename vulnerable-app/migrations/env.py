"""Credentials are taken only by explicit maintenance commands."""

import os

from alembic import context

from vulnlab_vulnerable.database import Database, DatabaseConfig
from vulnlab_vulnerable.models import Base

if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported; use the local database")

connection = context.config.attributes.get("connection")
database = None
try:
    if connection is None:
        database = Database(DatabaseConfig.from_mapping(os.environ))
        connection = database.engine.connect()
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
finally:
    if database is not None:
        if connection is not None:
            connection.close()
        database.dispose()
