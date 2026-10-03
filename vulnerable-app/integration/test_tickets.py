"""Reference functional/authorization tests on disposable PostgreSQL and Redis."""

import time

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from werkzeug.datastructures import MultiDict

from vulnlab_vulnerable.models import Comment, Ticket, User

from .test_auth import BASE, COOKIE, csrf, login, post, sid
from .test_auth import auth_app as auth_app

ALICE = -2001
BOB = -2002
OPERATIONS = [
    "/tickets",
    "/tickets/new",
    "/tickets/-2001",
    "/tickets/-2001/edit",
    "/tickets/-2001/delete",
    "/tickets/-2001/comments",
]


def actor_client(app, actor="alice"):
    client = app.test_client()
    login(
        client,
        actor,
        {
            "alice": "demo-Alice-only!",
            "bob": "demo-Bob-only!",
            "admin": "demo-Admin-only!",
        }[actor],
    )
    return client


def ticket_post(client, path, data=None):
    token = csrf(client, "/tickets/new")
    payload = MultiDict(data or {})
    payload.add("csrf_token", token)
    return post(client, path, payload)


def test_creation_owner_open_and_escaping(auth_app):
    client = actor_client(auth_app)
    response = ticket_post(
        client,
        "/tickets/new",
        dict(title="<b>Local title</b>", description="<script>local-only</script>"),
    )
    assert response.status_code == 303
    identifier = int(response.headers["Location"].rsplit("/", 1)[1])
    with auth_app.extensions["database"].transaction() as session:
        ticket = session.get(Ticket, identifier)
        assert ticket.owner_id == -1001 and ticket.status == "open"
    body = client.get(response.headers["Location"], base_url=BASE).get_data(
        as_text=True
    )
    assert (
        "&lt;b&gt;Local title&lt;/b&gt;" in body
        and "&lt;script&gt;local-only&lt;/script&gt;" in body
    )
    listing = client.get("/tickets", base_url=BASE).get_data(as_text=True)
    assert (
        "&lt;b&gt;Local title&lt;/b&gt;" in listing and "Bob demo ticket" not in listing
    )


@pytest.mark.parametrize(
    "operation,fields",
    [
        ("new", {"owner_id": "-1002"}),
        ("new", {"status": "closed"}),
        ("new", {"id": "44"}),
        ("edit", {"owner_id": "-1002"}),
        ("edit", {"updated_at": "forged"}),
        ("comments", {"author_id": "-1002"}),
        ("comments", {"ticket_id": "-2002"}),
        ("comments", {"role": "admin"}),
        ("delete", {"id": "-2002"}),
    ],
)
@pytest.mark.parametrize("actor", ["alice", "admin"])
def test_sensitive_fields_rejected_for_every_role(auth_app, actor, operation, fields):
    client = actor_client(auth_app, actor)
    path = "/tickets/new" if operation == "new" else f"/tickets/{ALICE}/{operation}"
    data = (
        dict(title="Updated", description="Local", status="closed")
        if operation == "edit"
        else dict(title="New", description="Local")
        if operation == "new"
        else dict(content="Local")
        if operation == "comments"
        else {}
    )
    assert ticket_post(client, path, data | fields).status_code == 400
    with auth_app.extensions["database"].transaction() as session:
        assert session.get(Ticket, ALICE).owner_id == -1001
        assert session.get(Ticket, ALICE).title == "Alice demo ticket"
        assert session.scalar(select(func.count()).select_from(Ticket)) == 2
        assert session.scalar(select(func.count()).select_from(Comment)) == 3


@pytest.mark.parametrize(
    "operation,field",
    [
        ("new", "title"),
        ("edit", "status"),
        ("comments", "content"),
        ("delete", "submit"),
    ],
)
def test_duplicate_fields_are_rejected(auth_app, operation, field):
    client = actor_client(auth_app)
    path = "/tickets/new" if operation == "new" else f"/tickets/{ALICE}/{operation}"
    data = (
        MultiDict([("title", "Local"), ("description", "Local"), ("status", "open")])
        if operation == "edit"
        else MultiDict([("title", "Local"), ("description", "Local")])
        if operation == "new"
        else MultiDict([("content", "Local")])
        if operation == "comments"
        else MultiDict([("submit", "Delete")])
    )
    data.add(field, "repeated")
    assert ticket_post(client, path, data).status_code == 400


@pytest.mark.parametrize(
    "suffix,method",
    [
        ("/edit", "GET"),
        ("/edit", "POST"),
        ("/delete", "POST"),
        ("/comments", "POST"),
    ],
)
@pytest.mark.preserved_protection
def test_inaccessible_and_missing_ticket_identical_404(auth_app, suffix, method):
    client = actor_client(auth_app)
    responses = []
    for identifier in [BOB, -9999, 2**40]:
        path = f"/tickets/{identifier}{suffix}"
        response = (
            client.get(path, base_url=BASE)
            if method == "GET"
            else ticket_post(
                client,
                path,
                dict(title="Local", description="Local", status="closed")
                if suffix == "/edit"
                else dict(content="Local")
                if suffix == "/comments"
                else {},
            )
        )
        assert response.status_code == 404
        responses.append(response.get_data())
    assert responses[0] == responses[1] == responses[2]
    body = client.get("/tickets", base_url=BASE).get_data(as_text=True)
    assert "Total visible: 1" in body and "Bob" not in body


def test_admin_all_operations_author_and_cascade(auth_app):
    client = actor_client(auth_app, "admin")
    body = client.get("/tickets", base_url=BASE).get_data(as_text=True)
    assert (
        "Total visible: 2" in body
        and "Alice demo ticket" in body
        and "Bob demo ticket" in body
    )
    for identifier, owner in [(ALICE, -1001), (BOB, -1002)]:
        assert (
            client.get(f"/tickets/{identifier}/edit", base_url=BASE).status_code == 200
        )
        assert (
            ticket_post(
                client,
                f"/tickets/{identifier}/edit",
                dict(title="Updated", description="Local", status="closed"),
            ).status_code
            == 303
        )
        assert (
            ticket_post(
                client,
                f"/tickets/{identifier}/comments",
                dict(content="<b>Admin local</b>"),
            ).status_code
            == 303
        )
        with auth_app.extensions["database"].transaction() as session:
            assert session.get(Ticket, identifier).owner_id == owner
            comment = session.scalar(
                select(Comment).where(
                    Comment.ticket_id == identifier,
                    Comment.content == "<b>Admin local</b>",
                )
            )
            assert comment.author_id == -1003
        assert "&lt;b&gt;Admin local&lt;/b&gt;" in client.get(
            f"/tickets/{identifier}", base_url=BASE
        ).get_data(as_text=True)
    assert ticket_post(client, f"/tickets/{ALICE}/delete").status_code == 303
    with auth_app.extensions["database"].transaction() as session:
        assert session.get(Ticket, ALICE) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(Comment)
                .where(Comment.ticket_id == ALICE)
            )
            == 0
        )
        assert session.get(Ticket, BOB) is not None
        assert session.scalar(select(func.count()).select_from(User)) == 3
    response = ticket_post(
        client, "/tickets/new", dict(title="Admin own", description="Local")
    )
    assert response.status_code == 303
    with auth_app.extensions["database"].transaction() as session:
        record = session.get(
            Ticket, int(response.headers["Location"].rsplit("/", 1)[1])
        )
        assert record.owner_id == -1003 and record.status == "open"


def test_user_own_edit_comment_and_delete_preserve_other_objects(auth_app):
    client = actor_client(auth_app)
    assert (
        ticket_post(
            client,
            f"/tickets/{ALICE}/edit",
            dict(title="User edit", description="Local", status="in_progress"),
        ).status_code
        == 303
    )
    assert (
        ticket_post(
            client, f"/tickets/{ALICE}/comments", dict(content="User local comment")
        ).status_code
        == 303
    )
    with auth_app.extensions["database"].transaction() as session:
        assert session.get(Ticket, ALICE).owner_id == -1001
        record = session.scalar(
            select(Comment).where(Comment.content == "User local comment")
        )
        assert record.author_id == -1001 and record.ticket_id == ALICE
    assert ticket_post(client, f"/tickets/{ALICE}/delete").status_code == 303
    with auth_app.extensions["database"].transaction() as session:
        assert session.get(Ticket, ALICE) is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(Comment)
                .where(Comment.ticket_id == ALICE)
            )
            == 0
        )
        assert session.get(Ticket, BOB).title == "Bob demo ticket"
        assert session.scalar(select(func.count()).select_from(User)) == 3


@pytest.mark.preserved_protection
def test_role_is_reloaded_before_ticket_authorization(auth_app):
    client = actor_client(auth_app, "admin")
    assert client.get(f"/tickets/{BOB}", base_url=BASE).status_code == 200
    with auth_app.extensions["database"].transaction() as session:
        session.get(User, -1003).role = "user"
    # Baseline detail refusal is intentionally replaced only for GET; writes retain policy.
    assert client.get(f"/tickets/{BOB}/edit", base_url=BASE).status_code == 404
    assert "Total visible: 0" in client.get("/tickets", base_url=BASE).get_data(
        as_text=True
    )
    assert (
        ticket_post(
            client, f"/tickets/{BOB}/comments", {"content": "Denied"}
        ).status_code
        == 404
    )


@pytest.mark.parametrize("operation", ["new", "edit", "delete", "comments"])
@pytest.mark.parametrize("token", [None, "invalid"])
def test_csrf_on_every_ticket_post(auth_app, operation, token):
    client = actor_client(auth_app)
    path = "/tickets/new" if operation == "new" else f"/tickets/{ALICE}/{operation}"
    data = {} if token is None else {"csrf_token": token}
    assert post(client, path, data).status_code == 400
    with auth_app.extensions["database"].transaction() as session:
        assert session.scalar(select(func.count()).select_from(Ticket)) == 2
        assert session.scalar(select(func.count()).select_from(Comment)) == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("title", "x" * 201),
        ("description", ""),
        ("description", "x" * 10001),
        ("description", "\x00"),
        ("status", "unknown"),
    ],
    ids=[
        "empty-title",
        "long-title",
        "empty-description",
        "long-description",
        "null-text",
        "unknown-status",
    ],
)
def test_edit_validation_atomic(auth_app, field, value):
    client = actor_client(auth_app)
    response = ticket_post(
        client,
        f"/tickets/{ALICE}/edit",
        dict(title="Changed", description="Local", status="closed") | {field: value},
    )
    assert response.status_code == 400
    with auth_app.extensions["database"].transaction() as session:
        record = session.get(Ticket, ALICE)
        assert record.title == "Alice demo ticket" and record.status == "open"


@pytest.mark.parametrize(
    "content", ["", "x" * 5001, "\x00"], ids=["empty", "too-long", "null-text"]
)
def test_comment_invalid_length(auth_app, content):
    client = actor_client(auth_app)
    assert (
        ticket_post(
            client, f"/tickets/{ALICE}/comments", dict(content=content)
        ).status_code
        == 400
    )


def test_unicode_maxima_and_user_comment_author(auth_app):
    client = actor_client(auth_app)
    response = ticket_post(
        client, "/tickets/new", dict(title="🙂" * 200, description="🙂" * 10000)
    )
    assert response.status_code == 303
    path = response.headers["Location"]
    assert (
        ticket_post(client, path + "/comments", dict(content="🙂" * 5000)).status_code
        == 303
    )
    with auth_app.extensions["database"].transaction() as session:
        record = session.get(Ticket, int(path.rsplit("/", 1)[1]))
        assert len(record.description) == 10000
        record = session.scalar(select(Comment).where(Comment.ticket_id == record.id))
        assert record.author_id == -1001 and len(record.content) == 5000


@pytest.mark.parametrize("state", ["visitor", "logout", "expired", "disabled"])
@pytest.mark.preserved_protection
def test_all_routes_reject_invalid_identity(auth_app, state):
    client = auth_app.test_client() if state == "visitor" else actor_client(auth_app)
    redis = auth_app.extensions["auth_redis"]
    if state == "disabled":
        with auth_app.extensions["database"].transaction() as session:
            session.get(User, -1001).active = False
    elif state == "expired":
        key = auth_app.config["SESSION_KEY_PREFIX"] + sid(client)
        record = auth_app.session_interface.serializer.decode(redis.get(key))
        record["_expires_at"] = time.time() - 1
        redis.set(key, auth_app.session_interface.serializer.encode(record), ex=60)
    elif state == "logout":
        old = sid(client)
        assert (
            post(
                client, "/logout", {"csrf_token": csrf(client, "/account")}
            ).status_code
            == 303
        )
        client.set_cookie(COOKIE, old, domain="vulnerable.vulnlab.test")
    for path in OPERATIONS:
        response = (
            post(client, path, {})
            if path.endswith(("/delete", "/comments"))
            else client.get(path, base_url=BASE)
        )
        assert response.status_code == 303
        assert response.headers["Location"] == "/login?next=/account"
        assert response.headers["Cache-Control"] == "no-store"
    for path in ["/tickets/new", "/tickets/-2001/edit"]:
        assert post(client, path, {}).status_code == 303
    with auth_app.extensions["database"].transaction() as session:
        assert session.scalar(select(func.count()).select_from(Ticket)) == 2
        assert session.scalar(select(func.count()).select_from(Comment)) == 3


@pytest.mark.parametrize("failure", ["sql", "redis-open", "redis-ping"])
@pytest.mark.preserved_protection
def test_backend_failure_denies_all_routes(auth_app, monkeypatch, failure):
    client = actor_client(auth_app)
    redis = auth_app.extensions["auth_redis"]
    identifier = sid(client)
    key = auth_app.config["SESSION_KEY_PREFIX"] + identifier
    stored = redis.get(key)

    def restore_authenticated_session():
        # Each route starts authenticated even when the previous failure invalidated it.
        redis.set(key, stored, ex=60)
        client.set_cookie(COOKIE, identifier, domain="vulnerable.vulnlab.test")

    if failure == "sql":

        def reject(*args, **kwargs):
            raise OperationalError("offline", {}, Exception("offline"))

        monkeypatch.setattr(auth_app.extensions["database"], "sessions", reject)
    else:

        def reject(*args, **kwargs):
            raise RedisConnectionError("offline")

        monkeypatch.setattr(
            auth_app.extensions["auth_redis"],
            "get" if failure == "redis-open" else "ping",
            reject,
        )
    for path in OPERATIONS:
        restore_authenticated_session()
        response = (
            post(client, path, {})
            if path.endswith(("/delete", "/comments"))
            else client.get(path, base_url=BASE)
        )
        assert response.status_code == 503
        assert "Alice" not in response.get_data(as_text=True)
    for path in ["/tickets/new", "/tickets/-2001/edit"]:
        restore_authenticated_session()
        assert post(client, path, {}).status_code == 503
    assert client.get("/healthz", base_url=BASE).get_json() == {"status": "ok"}
    with auth_app.extensions["database"].engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(Ticket)) == 2
        assert connection.scalar(select(func.count()).select_from(Comment)) == 3


def test_get_and_rollback_never_partially_mutate(auth_app, monkeypatch):
    client = actor_client(auth_app)
    for path in [
        "/tickets",
        "/tickets/new",
        f"/tickets/{ALICE}",
        f"/tickets/{ALICE}/edit",
    ]:
        assert client.get(path, base_url=BASE).status_code == 200
    for suffix in ["delete", "comments"]:
        assert (
            client.get(f"/tickets/{ALICE}/{suffix}", base_url=BASE).status_code == 405
        )
    db = auth_app.extensions["database"]
    from sqlalchemy import event

    def reject(session, context):
        raise OperationalError("offline after flush", {}, Exception("offline"))

    event.listen(db.sessions, "after_flush_postexec", reject)
    try:
        assert (
            ticket_post(
                client,
                f"/tickets/{ALICE}/edit",
                dict(title="Never committed", description="Local", status="closed"),
            ).status_code
            == 503
        )
    finally:
        event.remove(db.sessions, "after_flush_postexec", reject)
    with db.transaction() as session:
        record = session.get(Ticket, ALICE)
        assert record.title == "Alice demo ticket" and record.status == "open"
        assert session.scalar(select(func.count()).select_from(Comment)) == 3


def test_pagination_filtered_counts_and_stable_bounded_comments(auth_app):
    db = auth_app.extensions["database"]
    with db.transaction() as session:
        for i in range(24):
            session.add(
                Ticket(
                    owner_id=-1001,
                    title=f"Visible marker {i:02}",
                    description="Local",
                    status="open",
                )
            )
            session.add(
                Ticket(
                    owner_id=-1002,
                    title=f"Hidden marker {i:02}",
                    description="Local",
                    status="open",
                )
            )
            session.add(
                Comment(
                    ticket_id=ALICE, author_id=-1001, content=f"Comment marker {i:02}"
                )
            )
    client = actor_client(auth_app)
    first = client.get("/tickets", base_url=BASE).get_data(as_text=True)
    second = client.get("/tickets?page=2", base_url=BASE).get_data(as_text=True)
    assert first == client.get("/tickets", base_url=BASE).get_data(as_text=True)
    assert "Total visible: 25" in first and "Hidden marker" not in first + second
    assert first.count("Visible marker") <= 20 and second.count("Visible marker") <= 5
    comments = client.get(f"/tickets/{ALICE}", base_url=BASE).get_data(as_text=True)
    more = client.get(f"/tickets/{ALICE}?comments_page=2", base_url=BASE).get_data(
        as_text=True
    )
    assert comments.count("Comment marker") == 18 and more.count("Comment marker") == 6
