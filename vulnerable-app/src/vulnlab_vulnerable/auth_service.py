"""Explicit SQL transactions; no authorization on tickets is implemented here."""

from dataclasses import dataclass

from flask_login import UserMixin
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .models import User
from .passwords import hash_password, hasher, verify_password

# Public fictitious dummy input, hashed once per worker with the same Argon2 profile.
# Its hash is never returned, logged or stored in Redis.
DUMMY_HASH = hash_password("fictitious-unknown-user-check")


@dataclass
class Identity(UserMixin):
    id: int
    username: str
    display_name: str
    role: str
    active: bool
    session_version: int = 0

    @property
    def is_active(self):
        return self.active


def identity(record):
    return Identity(
        record.id,
        record.username,
        record.display_name,
        record.role,
        record.active,
        record.session_version,
    )


def register_user(database, username, display_name, password):
    encoded = hash_password(password)
    try:
        with database.transaction() as session:
            session.add(
                User(
                    username=username,
                    display_name=display_name,
                    password_hash=encoded,
                    role="user",
                    active=True,
                )
            )
            session.flush()
    except IntegrityError as error:
        if error.orig.sqlstate == "23505":
            return False
        raise
    return True


def authenticate(database, username, password):
    with database.transaction() as session:
        record = session.scalar(select(User).where(User.username == username))
        valid = verify_password(
            record.password_hash if record else DUMMY_HASH, password
        )
        if not valid or record is None or not record.active:
            return None
        if hasher.check_needs_rehash(record.password_hash):
            record.password_hash = hash_password(password)
        return identity(record)


def load_identity(database, identifier):
    try:
        identifier = int(identifier)
    except (TypeError, ValueError):
        return None
    with database.transaction() as session:
        record = session.get(User, identifier)
        return identity(record) if record and record.active else None
