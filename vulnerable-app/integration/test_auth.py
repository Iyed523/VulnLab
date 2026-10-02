"""Functional acceptance with real PostgreSQL/Redis and active CSRF/limits."""

import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from argon2 import PasswordHasher
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from vulnlab_vulnerable import create_app
from vulnlab_vulnerable.auth_service import register_user
from vulnlab_vulnerable.models import User
from vulnlab_vulnerable.passwords import verify_password
from vulnlab_vulnerable.seed import seed_demo

BASE = "https://vulnerable.vulnlab.test:8443"
COOKIE = "__Host-vulnlab-session"


@pytest.fixture
def auth_app(databases, clean_test_records, tmp_path):
    database, _ = databases
    seed_demo(database)
    key = tmp_path / "session-key"
    key.write_text(secrets.token_hex(32), encoding="ascii")
    marker = "m6test-" + secrets.token_hex(8)
    app = create_app(
        dict(
            DB_HOST=os.environ["DB_HOST"],
            DB_NAME=os.environ["DB_NAME"],
            DB_USER=os.environ["DB_USER"],
            DB_PASSWORD=os.environ["DB_PASSWORD"],
            REDIS_HOST=os.environ["REDIS_HOST"],
            REDIS_PASSWORD=os.environ["REDIS_PASSWORD"],
            SESSION_KEY_FILE=str(key),
            SESSION_KEY_PREFIX=marker + ":session:",
            RATE_KEY_PREFIX=marker,
            TRUST_PROXY=False,
        )
    )
    yield app
    client = app.extensions["auth_redis"]
    owned = list(client.scan_iter(match="*" + marker + "*"))
    if owned:
        client.delete(*owned)
    client.close()
    app.extensions["database"].dispose()


def csrf(client, path="/login"):
    response = client.get(path, base_url=BASE)
    assert response.status_code == 200
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match, "CSRF field missing (token deliberately not logged)"
    return match.group(1)


def post(client, path, data):
    return client.post(
        path, data=data, base_url=BASE, headers={"Referer": BASE + path.split("?")[0]}
    )


def login(client, username="alice", password="demo-Alice-only!"):
    token = csrf(client)
    response = post(
        client, "/login", dict(username=username, password=password, csrf_token=token)
    )
    assert response.status_code == 303
    return response


def sid(client):
    cookie = client.get_cookie(COOKIE, domain="vulnerable.vulnlab.test")
    assert cookie, "Session cookie missing (value deliberately not logged)"
    return cookie.value


def test_register_normalizes_hashes_and_never_auto_logs_in(auth_app):
    client = auth_app.test_client()
    token = csrf(client, "/register")
    response = post(
        client,
        "/register",
        dict(
            username=" NewUser ",
            display_name="<b>Fictitious</b>",
            password="demo-new-user-only!",
            csrf_token=token,
        ),
    )
    assert response.status_code == 303 and response.headers["Location"] == "/login"
    assert client.get("/account", base_url=BASE).status_code == 303
    with auth_app.extensions["database"].transaction() as session:
        record = session.scalar(select(User).where(User.username == "newuser"))
        assert record.role == "user" and record.active
        assert record.password_hash.startswith("$argon2id$")
        assert verify_password(record.password_hash, "demo-new-user-only!")
    login(client, "NEWUSER", "demo-new-user-only!")
    body = client.get("/account", base_url=BASE).get_data(as_text=True)
    assert "&lt;b&gt;Fictitious&lt;/b&gt;" in body
    assert "<b>Fictitious</b>" not in body


@pytest.mark.parametrize(
    "field,value",
    [("role", "admin"), ("active", "false"), ("id", "1"), ("password_hash", "forged")],
)
def test_privilege_fields_explicitly_rejected(auth_app, field, value):
    client = auth_app.test_client()
    token = csrf(client, "/register")
    response = post(
        client,
        "/register",
        dict(
            username="newuser",
            display_name="Demo",
            password="demo-new-user-only!",
            csrf_token=token,
        )
        | {field: value},
    )
    assert response.status_code == 400
    with auth_app.extensions["database"].transaction() as session:
        assert session.scalar(select(User).where(User.username == "newuser")) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("password", "short"),
        ("password", "x" * 129),
        ("username", "x" * 129),
        ("display_name", "x" * 101),
    ],
)
def test_validation_precedes_argon2(auth_app, monkeypatch, field, value):
    def reject(*args):
        raise AssertionError("Invalid input reached expensive hashing")

    monkeypatch.setattr("vulnlab_vulnerable.auth_service.hash_password", reject)
    client = auth_app.test_client()
    token = csrf(client, "/register")
    response = post(
        client,
        "/register",
        dict(
            username="newuser",
            display_name="Demo",
            password="demo-new-user-only!",
            csrf_token=token,
        )
        | {field: value},
    )
    assert response.status_code == 400


def test_duplicate_and_concurrent_collision_roll_back(auth_app):
    client = auth_app.test_client()
    token = csrf(client, "/register")
    assert (
        post(
            client,
            "/register",
            dict(
                username="Alice",
                display_name="Different",
                password="demo-other-password!",
                csrf_token=token,
            ),
        ).status_code
        == 409
    )
    database = auth_app.extensions["database"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda _: register_user(
                    database, "concurrent", "Fictitious", "demo-concurrent-only!"
                ),
                range(2),
            )
        )
    assert sorted(outcomes) == [False, True]
    with database.transaction() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.username == "concurrent")
            )
            == 1
        )
        assert (
            session.scalar(select(User).where(User.username == "alice")).display_name
            == "Alice"
        )


@pytest.mark.parametrize(
    "username,password",
    [("unknown", "demo-Alice-only!"), ("alice", "demo-wrong-password!")],
    ids=["unknown-user", "wrong-password"],
)
def test_invalid_login_generic_and_runs_argon2(
    auth_app, monkeypatch, username, password
):
    from vulnlab_vulnerable import auth_service

    original = auth_service.verify_password
    calls = []

    def observed(*args):
        calls.append(True)
        return original(*args)

    monkeypatch.setattr(auth_service, "verify_password", observed)
    client = auth_app.test_client()
    token = csrf(client)
    response = post(
        client, "/login", dict(username=username, password=password, csrf_token=token)
    )
    assert response.status_code == 401
    assert "Invalid credentials." in response.get_data(as_text=True)
    assert calls == [True]
    assert client.get("/account", base_url=BASE).status_code == 303


def test_cookie_rotation_logout_and_replays(auth_app):
    client = auth_app.test_client()
    csrf(client)
    old = sid(client)
    response = login(client)
    new = sid(client)
    assert old != new, "SID was not rotated"
    redis = auth_app.extensions["auth_redis"]
    prefix = auth_app.config["SESSION_KEY_PREFIX"]
    assert not redis.exists(prefix + old)
    assert redis.exists(prefix + new)
    header = response.headers["Set-Cookie"]
    for attribute in ("Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
        assert attribute in header
    assert "Domain=" not in header and "remember" not in header
    stored = redis.get(prefix + new)
    assert b"demo-Alice-only!" not in stored and b"argon2" not in stored
    replay = auth_app.test_client()
    replay.set_cookie(COOKIE, old, domain="vulnerable.vulnlab.test")
    assert replay.get("/account", base_url=BASE).status_code == 303
    account = client.get("/account", base_url=BASE)
    assert account.status_code == 200
    body = account.get_data(as_text=True)
    assert "Alice" in body and "Bob" not in body and "password_hash" not in body
    assert client.get("/logout", base_url=BASE).status_code == 405
    assert client.get("/account", base_url=BASE).status_code == 200
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body).group(1)
    response = post(client, "/logout", {"csrf_token": token})
    assert response.status_code == 303
    assert not redis.exists(prefix + new)
    assert client.get_cookie(COOKIE, domain="vulnerable.vulnlab.test") is None
    replay.set_cookie(COOKIE, new, domain="vulnerable.vulnlab.test")
    assert replay.get("/account", base_url=BASE).status_code == 303


@pytest.mark.parametrize("path", ["/register", "/login", "/logout"])
@pytest.mark.parametrize("token", [None, "invalid"])
def test_csrf_never_disabled(auth_app, path, token):
    client = auth_app.test_client()
    if path == "/logout":
        login(client)
    data = dict(username="alice", display_name="Alice", password="demo-Alice-only!")
    if token is not None:
        data["csrf_token"] = token
    assert post(client, path, data).status_code == 400
    if path == "/logout":
        assert client.get("/account", base_url=BASE).status_code == 200


def test_disabled_user_login_and_existing_session_invalidated(auth_app):
    client = auth_app.test_client()
    login(client)
    identifier = sid(client)
    with auth_app.extensions["database"].transaction() as session:
        session.get(User, -1001).active = False
    assert client.get("/account", base_url=BASE).status_code == 303
    assert not auth_app.extensions["auth_redis"].exists(
        auth_app.config["SESSION_KEY_PREFIX"] + identifier
    )
    token = csrf(client)
    response = post(
        client,
        "/login",
        dict(username="alice", password="demo-Alice-only!", csrf_token=token),
    )
    assert response.status_code == 401 and "Invalid credentials." in response.get_data(
        as_text=True
    )


def test_expiration_is_real_redis_ttl(auth_app):
    auth_app.config["AUTH_SESSION_SECONDS"] = 2
    auth_app.config["PERMANENT_SESSION_LIFETIME"] = 2
    client = auth_app.test_client()
    login(client)
    identifier = sid(client)
    key = auth_app.config["SESSION_KEY_PREFIX"] + identifier
    assert 0 < auth_app.extensions["auth_redis"].ttl(key) <= 2
    time.sleep(2.2)
    assert not auth_app.extensions["auth_redis"].exists(key)
    assert client.get("/account", base_url=BASE).status_code == 303


def test_rehash_after_successful_login(auth_app):
    old = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(
        "demo-Alice-only!"
    )
    with auth_app.extensions["database"].transaction() as session:
        session.get(User, -1001).password_hash = old
    login(auth_app.test_client())
    with auth_app.extensions["database"].transaction() as session:
        updated = session.get(User, -1001).password_hash
        assert updated != old, "Password hash was not upgraded"
        assert "m=65536,t=3,p=4" in updated


def test_external_redirect_is_refused(auth_app):
    client = auth_app.test_client()
    assert (
        client.get("/login?next=https://example.invalid", base_url=BASE).status_code
        == 400
    )


@pytest.mark.parametrize("path,attempts", [("/login", 5), ("/register", 3)])
def test_rate_limits_and_forged_headers(auth_app, path, attempts):
    client = auth_app.test_client()
    token = csrf(client, path)
    for index in range(attempts):
        response = client.post(
            path,
            base_url=BASE,
            data={"csrf_token": token},
            headers={"Referer": BASE + path, "X-Forwarded-For": f"192.0.2.{index + 1}"},
        )
        assert response.status_code in (400, 401)
    response = post(client, path, {"csrf_token": token})
    assert response.status_code == 429


@pytest.mark.parametrize("failure", ["sql", "redis-open", "redis-save", "limiter"])
def test_backend_failure_is_controlled_and_health_independent(
    auth_app, monkeypatch, failure
):
    client = auth_app.test_client()
    login(client)
    if failure == "sql":

        def reject(*args, **kwargs):
            raise OperationalError("unavailable", {}, Exception("offline"))

        monkeypatch.setattr(auth_app.extensions["database"], "sessions", reject)
    else:

        def reject(*args, **kwargs):
            raise RedisConnectionError("offline")

        if failure == "redis-open":
            monkeypatch.setattr(auth_app.session_interface.client, "get", reject)
        elif failure == "redis-save":
            monkeypatch.setattr(auth_app.session_interface.client, "set", reject)
            # Force a session write by starting a new CSRF context.
            response = client.get("/account", base_url=BASE)
            assert response.status_code == 200
            auth_app.session_interface.client.delete(
                auth_app.config["SESSION_KEY_PREFIX"] + sid(client)
            )
            response = client.get("/login", base_url=BASE)
            assert response.status_code == 503
        else:
            limiter = next(iter(auth_app.extensions["limiter"]))
            monkeypatch.setattr(limiter.storage.storage, "evalsha", reject)
    if failure != "redis-save":
        if failure == "limiter":
            # Obtain a token before inducing the storage operation failure.
            token = csrf(client)
            response = post(
                client,
                "/login",
                dict(username="alice", password="demo-Alice-only!", csrf_token=token),
            )
        else:
            response = client.get("/account", base_url=BASE)
        assert response.status_code == 503
    assert "Alice" not in response.get_data(as_text=True)
    assert client.get("/healthz", base_url=BASE).get_json() == {"status": "ok"}
