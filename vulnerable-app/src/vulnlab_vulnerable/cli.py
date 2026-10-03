"""Explicit database maintenance; never called by HTTP workers."""

import argparse
import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy.exc import SQLAlchemyError

from .database import Database, DatabaseConfig
from .seed import SeedCollision, seed_demo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("upgrade", "check", "seed"))
    parser.add_argument("--config", default="alembic.ini")
    args = parser.parse_args()
    database = None
    try:
        if args.action == "seed":
            database = Database(DatabaseConfig.from_mapping(os.environ))
            seed_demo(database)
        else:
            config = Config(args.config)
            if args.action == "upgrade":
                command.upgrade(config, "head")
            else:
                command.check(config)
    except SeedCollision as error:
        print(str(error), file=sys.stderr)
        return 1
    except (SQLAlchemyError, ValueError):
        # Do not leak connection strings, SQL parameters or credentials in errors.
        print(
            "Database command failed; check configuration/schema or fixture collision.",
            file=sys.stderr,
        )
        return 1
    finally:
        if database is not None:
            database.dispose()
    print(f"Database command {args.action} completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
