"""No database needed: configuration, normalization and password primitives."""

import pytest
from sqlalchemy import event

from vulnlab_vulnerable import create_app
from vulnlab_vulnerable.database import Database, DatabaseConfig
from vulnlab_vulnerable.models import User, normalize_username
from vulnlab_vulnerable.passwords import hash_password, verify_password


@pytest.mark.parametrize("raw", [" Alice ", "ALICE", "Ａｌｉｃｅ"])
def test_username_normalization(raw):
    assert normalize_username(raw) == "alice"
    assert User(username=raw).username == "alice"


@pytest.mark.parametrize("raw", ["ab", "a" * 33, "a b", "éclair", "../alice", ""])
def test_invalid_username(raw):
    with pytest.raises(ValueError):
        normalize_username(raw)


def test_argon2id_hash_and_verification():
    encoded = hash_password("fictitious-test-password")
    assert encoded.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert verify_password(encoded, "fictitious-test-password")
    assert not verify_password(encoded, "wrong")
    assert not verify_password("invalid hash", "wrong")
    assert hash_password("fictitious-test-password") != encoded


def test_configuration_redacts_password_and_escapes_url():
    config = DatabaseConfig("localhost", "test", "test", "fictitious:@/%")
    assert config.url().password == "fictitious:@/%"
    assert "fictitious" not in repr(config)
    assert "fictitious" not in str(config.url())


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"DB_HOST": "db"},
        {
            "DB_HOST": "db",
            "DB_NAME": "test",
            "DB_USER": "test",
            "DB_PASSWORD": "demo",
            "DB_PORT": "invalid",
        },
    ],
)
def test_invalid_configuration_is_explicit(values):
    with pytest.raises(ValueError):
        DatabaseConfig.from_mapping(values)


def test_factory_isolated_and_health_never_connects():
    values = dict(
        DB_HOST="unreachable.invalid",
        DB_NAME="demo",
        DB_USER="demo",
        DB_PASSWORD="demo-only",
    )
    first = create_app(values)
    second = create_app(values)
    assert first.extensions["database"] is not second.extensions["database"]

    def reject(*args):
        raise AssertionError("Health must never open a SQL connection")

    for app in (first, second):
        event.listen(app.extensions["database"].engine, "do_connect", reject)
        assert app.test_client().get("/healthz").get_json() == {"status": "ok"}
        app.extensions["database"].dispose()


def test_transaction_closes_and_rolls_back_on_error(monkeypatch):
    from contextlib import contextmanager

    calls = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append("close")

        @contextmanager
        def begin(self):
            try:
                yield
            except RuntimeError:
                calls.append("rollback")
                raise

    database = Database(DatabaseConfig("unreachable.invalid", "demo", "demo", "demo"))
    monkeypatch.setattr(database, "sessions", Session)
    with pytest.raises(RuntimeError):
        with database.transaction():
            raise RuntimeError("fictitious failure")
    assert calls == ["rollback", "close"]
    database.dispose()
