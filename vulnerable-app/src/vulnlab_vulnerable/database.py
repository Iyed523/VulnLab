"""Application-owned configuration and explicit transaction boundaries."""

import os
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    name: str
    user: str
    password: str = field(repr=False)
    port: int = 5432

    @classmethod
    def from_mapping(cls, values):
        required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
        if any(not values.get(key) for key in required):
            raise ValueError("Explicit PostgreSQL configuration required")
        try:
            port = int(values.get("DB_PORT", 5432))
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("Invalid PostgreSQL port") from None
        return cls(*(values[key] for key in required), port=port)

    def url(self):
        return URL.create(
            "postgresql+psycopg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        )


class Database:
    def __init__(self, config):
        # Creating an engine/pool opens no connection. Parameters are never logged.
        self.engine = create_engine(
            config.url(),
            echo=False,
            hide_parameters=True,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"},
        )
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def transaction(self):
        # begin handles commit/rollback; the outer context always closes the session.
        with self.sessions() as session, session.begin():
            yield session

    def dispose(self):
        self.engine.dispose()


def init_database(app):
    values = app.config
    if any(values.get(key) for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")):
        app.extensions["database"] = Database(DatabaseConfig.from_mapping(values))


def environment_config():
    return {
        key: os.environ[key]
        for key in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_PORT")
        if key in os.environ
    }
