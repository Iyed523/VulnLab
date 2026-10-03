"""Argon2id primitives; no login or authentication flow in M5."""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.profiles import RFC_9106_LOW_MEMORY

hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)
assert hasher.type == Type.ID


def hash_password(password):
    return hasher.hash(password)


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False
