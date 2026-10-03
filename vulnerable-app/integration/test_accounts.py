"""M8 functional controls on exclusively disposable PostgreSQL/Redis."""

import time
from contextlib import contextmanager

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import Forbidden

from vulnlab_vulnerable import account_service as service
from vulnlab_vulnerable.auth_service import identity
from vulnlab_vulnerable.models import User

from .test_auth import BASE, COOKIE, csrf, post, sid
from .test_auth import auth_app as auth_app
from .test_tickets import actor_client

pytestmark = pytest.mark.preserved_protection


ROUTES = ["/account", "/tickets", "/account/edit", "/admin/users"]
ACTIONS = ["activate", "deactivate"]


def submit(client, path, data=None, source="/account/edit"):
    payload = MultiDict(data or {})
    payload.add("csrf_token", csrf(client, source))
    return post(client, path, payload)


def status(admin, action, identifier=-1001, data=None):
    return submit(admin, f"/admin/users/{identifier}/{action}", data, "/admin/users")


def snapshot(app):
    with app.extensions["database"].transaction() as session:
        return {
            table: [
                tuple(row)
                for row in session.execute(text(f"SELECT * FROM {table} ORDER BY id"))
            ]
            for table in ("users", "tickets", "comments")
        }


def test_own_profile_only_and_escaping(auth_app):
    client = actor_client(auth_app)
    before = snapshot(auth_app)
    response = submit(client, "/account/edit", {"display_name": "<b>Updated</b>"})
    assert response.status_code == 303 and response.headers["Location"] == "/account"
    body = client.get("/account", base_url=BASE).get_data(as_text=True)
    assert "&lt;b&gt;Updated&lt;/b&gt;" in body and "<b>Updated</b>" not in body
    with auth_app.extensions["database"].transaction() as session:
        record = session.get(User, -1001)
        assert record.username == "alice" and record.role == "user" and record.active
        assert record.session_version == 0
        assert session.get(User, -1002).display_name == "Bob"
    after = snapshot(auth_app)
    assert (
        before["tickets"] == after["tickets"]
        and before["comments"] == after["comments"]
    )
    assert 'href="/admin/users"' not in body


@pytest.mark.parametrize(
    "field",
    [
        "username",
        "password",
        "password_hash",
        "role",
        "active",
        "id",
        "created_at",
        "updated_at",
        "session_version",
    ],
)
def test_sensitive_profile_fields_atomic(auth_app, field):
    client = actor_client(auth_app)
    before = snapshot(auth_app)
    assert (
        submit(
            client, "/account/edit", {"display_name": "Changed", field: "forged"}
        ).status_code
        == 400
    )
    assert snapshot(auth_app) == before


@pytest.mark.parametrize("value", ["", "x" * 101, "nul\x00value"])
def test_invalid_name_no_write(auth_app, value):
    client = actor_client(auth_app)
    before = snapshot(auth_app)
    assert submit(client, "/account/edit", {"display_name": value}).status_code == 400
    assert snapshot(auth_app) == before


@pytest.mark.parametrize("value", ["x", "界" * 100])
def test_name_bounds(auth_app, value):
    client = actor_client(auth_app)
    assert submit(client, "/account/edit", {"display_name": value}).status_code == 303
    with auth_app.extensions["database"].transaction() as session:
        assert session.get(User, -1001).display_name == value


def test_duplicate_name_and_token_no_write(auth_app):
    client = actor_client(auth_app)
    before = snapshot(auth_app)
    for data in [
        MultiDict([("display_name", "One"), ("display_name", "Two")]),
        MultiDict(
            [("display_name", "One"), ("csrf_token", csrf(client, "/account/edit"))]
        ),
    ]:
        assert submit(client, "/account/edit", data).status_code == 400
    assert snapshot(auth_app) == before


@pytest.mark.parametrize(
    "path",
    [
        "/account/edit",
        "/admin/users",
        "/admin/users/-1001/activate",
        "/admin/users/-1001/deactivate",
    ],
)
def test_visitor_requires_auth_before_csrf(auth_app, path):
    client = auth_app.test_client()
    response = (
        post(client, path, {})
        if path.endswith(tuple(ACTIONS))
        else client.get(path, base_url=BASE)
    )
    assert (
        response.status_code == 303
        and response.headers["Location"] == "/login?next=/account"
    )
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("identifier", [-1001, 123456, 2**40])
@pytest.mark.parametrize("action", ACTIONS)
def test_user_forbidden_even_missing_target(auth_app, identifier, action):
    client = actor_client(auth_app)
    before = snapshot(auth_app)
    assert client.get("/admin/users", base_url=BASE).status_code == 403
    assert submit(client, f"/admin/users/{identifier}/{action}").status_code == 403
    assert snapshot(auth_app) == before


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("identifier", [123456, 2**40])
def test_admin_missing_target(auth_app, action, identifier):
    admin = actor_client(auth_app, "admin")
    assert status(admin, action, identifier).status_code == 404


@pytest.mark.parametrize("action", ACTIONS)
def test_admin_target_refused(auth_app, action):
    admin = actor_client(auth_app, "admin")
    before = snapshot(auth_app)
    assert status(admin, action, -1003).status_code == 403
    assert snapshot(auth_app) == before


def test_repeatable_status_preserves_business_data(auth_app):
    admin = actor_client(auth_app, "admin")
    before = snapshot(auth_app)
    for action, active, version in [
        ("deactivate", False, 1),
        ("deactivate", False, 1),
        ("activate", True, 1),
        ("activate", True, 1),
    ]:
        response = status(admin, action)
        assert (
            response.status_code == 303
            and response.headers["Location"] == "/admin/users"
        )
        with auth_app.extensions["database"].transaction() as session:
            record = session.get(User, -1001)
            assert record.active == active and record.session_version == version
            assert record.role == "user" and record.username == "alice"
    after = snapshot(auth_app)
    assert (
        before["tickets"] == after["tickets"]
        and before["comments"] == after["comments"]
    )


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("field", ["id", "active", "role", "submit"])
def test_status_strict_fields(auth_app, action, field):
    admin = actor_client(auth_app, "admin")
    before = snapshot(auth_app)
    data = MultiDict([(field, "forged")])
    if field == "submit":
        data.add(field, "duplicate")
    assert status(admin, action, data=data).status_code == 400
    assert snapshot(auth_app) == before


@pytest.mark.parametrize(
    "path",
    ["/account/edit", "/admin/users/-1001/activate", "/admin/users/-1001/deactivate"],
)
@pytest.mark.parametrize("token", [None, "invalid"])
def test_each_post_csrf_required(auth_app, path, token):
    admin = actor_client(auth_app, "admin")
    before = snapshot(auth_app)
    data = {"display_name": "Changed"} if path == "/account/edit" else {}
    if token:
        data["csrf_token"] = token
    assert post(admin, path, data).status_code == 400
    assert snapshot(auth_app) == before


def test_get_never_changes_state(auth_app):
    admin = actor_client(auth_app, "admin")
    before = snapshot(auth_app)
    assert admin.get("/account/edit", base_url=BASE).status_code == 200
    assert admin.get("/admin/users", base_url=BASE).status_code == 200
    for action in ACTIONS:
        assert (
            admin.get(f"/admin/users/-1001/{action}", base_url=BASE).status_code == 405
        )
    assert snapshot(auth_app) == before


@pytest.mark.parametrize("path", ROUTES)
@pytest.mark.parametrize("reenable_first", [False, True])
def test_durable_revocation_all_protected_routes(auth_app, path, reenable_first):
    client = actor_client(auth_app)
    old = sid(client)
    admin = actor_client(auth_app, "admin")
    assert status(admin, "deactivate").status_code == 303
    if reenable_first:
        assert status(admin, "activate").status_code == 303
    response = client.get(path, base_url=BASE)
    assert response.status_code == 303
    assert not client.get_cookie(COOKIE, domain="vulnerable.vulnlab.test")
    redis = auth_app.extensions["auth_redis"]
    assert not redis.exists(auth_app.config["SESSION_KEY_PREFIX"] + old)
    if not reenable_first:
        assert status(admin, "activate").status_code == 303
    client.set_cookie(COOKIE, old, domain="vulnerable.vulnlab.test")
    assert client.get(path, base_url=BASE).status_code == 303
    fresh = actor_client(auth_app)
    assert fresh.get("/account/edit", base_url=BASE).status_code == 200


def test_legacy_and_expired_sessions_refused(auth_app):
    for mode in ("legacy", "expired"):
        client = actor_client(auth_app)
        with client.session_transaction(base_url=BASE) as state:
            if mode == "legacy":
                state.pop("_auth_version")
            else:
                state["_expires_at"] = time.time() - 1
        assert client.get("/account/edit", base_url=BASE).status_code == 303


@pytest.mark.parametrize("value", ["0", "1001", "-1", "abc", "1&page=2", "١"])
def test_pagination_rejects_invalid(auth_app, value):
    admin = actor_client(auth_app, "admin")
    assert admin.get("/admin/users?page=" + value, base_url=BASE).status_code == 400


def test_pagination_stable_bounded_private_projection(auth_app):
    admin = actor_client(auth_app, "admin")
    database = auth_app.extensions["database"]
    with database.transaction() as session:
        for index in range(25):
            session.add(
                User(
                    id=10000 + index,
                    username=f"pageuser{index}",
                    display_name="<b>Name</b>",
                    password_hash="fictitious-placeholder",
                    role="user",
                    active=True,
                )
            )
        actor = identity(session.get(User, -1003))
    rows, total = service.list_users(database, actor, 1)
    rows2, _ = service.list_users(database, actor, 2)
    assert total == 28 and len(rows) == 20 and len(rows2) == 8
    assert [r.id for r in rows + rows2] == sorted(r.id for r in rows + rows2)
    assert set(rows[0]._mapping) == {"id", "username", "display_name", "role", "active"}
    body = admin.get("/admin/users", base_url=BASE).get_data(as_text=True)
    assert "&lt;b&gt;Name&lt;/b&gt;" in body and 'href="/admin/users"' in body
    for private in (
        "password_hash",
        "$argon2",
        "session_version",
        "_auth_version",
        sid(admin),
        "fictitious-placeholder",
    ):
        assert private not in body
    assert admin.get("/admin/users?page=1000", base_url=BASE).status_code == 200


@pytest.mark.parametrize("operation", ["profile", "edit", "list", "status"])
@pytest.mark.parametrize("change", ["inactive", "version", "role"])
def test_transaction_rechecks_stale_actor(auth_app, operation, change):
    database = auth_app.extensions["database"]
    with database.transaction() as session:
        actor = identity(session.get(User, -1003))
    with database.transaction() as session:
        record = session.get(User, actor.id)
        if change == "inactive":
            record.active = False
        elif change == "version":
            record.session_version += 1
        else:
            record.role = "user"
    before = snapshot(auth_app)
    calls = {
        "profile": lambda: service.profile(database, actor),
        "edit": lambda: service.edit_profile(database, actor, "Changed"),
        "list": lambda: service.list_users(database, actor, 1),
        "status": lambda: service.change_active(database, actor, -1001, False),
    }
    if change == "role" and operation in ("profile", "edit"):
        calls[operation]()  # A current active user may still edit their own profile.
    else:
        with pytest.raises(Forbidden):
            calls[operation]()
        assert snapshot(auth_app) == before


@pytest.mark.parametrize("operation", ["edit", "status"])
def test_rollback_after_flush(auth_app, monkeypatch, operation):
    database = auth_app.extensions["database"]
    with database.transaction() as session:
        actor = identity(session.get(User, -1003))
    before = snapshot(auth_app)
    real = database.transaction

    @contextmanager
    def fail_commit():
        with real() as session:
            yield session
            session.flush()
            raise OperationalError("fictitious failure", None, None)

    monkeypatch.setattr(database, "transaction", fail_commit)
    with pytest.raises(OperationalError):
        if operation == "edit":
            service.edit_profile(database, actor, "Changed")
        else:
            service.change_active(database, actor, -1001, False)
    monkeypatch.setattr(database, "transaction", real)
    assert snapshot(auth_app) == before


@pytest.mark.parametrize(
    "path",
    [
        "/account/edit",
        "/admin/users",
        "/admin/users/-1001/activate",
        "/admin/users/-1001/deactivate",
    ],
)
@pytest.mark.parametrize("backend", ["sql", "redis", "redis-open"])
def test_backend_failure_new_routes(auth_app, monkeypatch, path, backend):
    admin = actor_client(auth_app, "admin")
    token = csrf(admin, "/admin/users")
    before = snapshot(auth_app)
    database = auth_app.extensions["database"]
    original = database.sessions

    def fail(*args, **kwargs):
        if backend == "sql":
            raise OperationalError("fictitious failure", None, None)
        raise RedisConnectionError("fictitious failure")

    if backend == "sql":
        monkeypatch.setattr(database, "sessions", fail)
    elif backend == "redis":
        monkeypatch.setattr(auth_app.extensions["auth_redis"], "ping", fail)
    else:
        monkeypatch.setattr(auth_app.extensions["auth_redis"], "get", fail)
    response = (
        post(admin, path, {"csrf_token": token})
        if path.endswith(tuple(ACTIONS))
        else admin.get(path, base_url=BASE)
    )
    assert (
        response.status_code == 503 and response.headers["Cache-Control"] == "no-store"
    )
    monkeypatch.setattr(database, "sessions", original)
    assert snapshot(auth_app) == before


def test_multiple_old_sessions_revoked_without_prior_replay(auth_app):
    clients = [actor_client(auth_app), actor_client(auth_app)]
    assert sid(clients[0]) != sid(clients[1])
    admin = actor_client(auth_app, "admin")
    assert status(admin, "deactivate").status_code == 303
    assert status(admin, "activate").status_code == 303
    for client in clients:
        assert client.get("/account", base_url=BASE).status_code == 303
