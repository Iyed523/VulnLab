"""Real PostgreSQL semantics, role privileges and transaction atomicity."""

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from vulnlab_vulnerable.models import Comment, Ticket, User
from vulnlab_vulnerable.passwords import verify_password
from vulnlab_vulnerable.seed import SeedCollision, seed_demo


def user(**overrides):
    return User(
        **(
            dict(
                username="tester",
                password_hash="fictitious-hash",
                display_name="Tester",
                role="user",
                active=True,
            )
            | overrides
        )
    )


def test_postgresql_schema_and_utc(databases):
    app, _ = databases
    with app.transaction() as session:
        record = user()
        session.add(record)
        session.flush()
        session.refresh(record)
        assert record.created_at.utcoffset().total_seconds() == 0
        assert record.updated_at.utcoffset().total_seconds() == 0
        assert session.scalar(text("SHOW timezone")) == "UTC"
        assert session.scalar(text("SELECT version()")).startswith("PostgreSQL 16.")
    columns = inspect(app.engine).get_columns("users")
    assert all(not column["nullable"] for column in columns)


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "owner"},
        {"display_name": None},
        {"display_name": ""},
        {"display_name": "x" * 101},
        {"password_hash": None},
        {"password_hash": ""},
        {"active": None},
    ],
)
def test_user_constraints(databases, changes):
    app, _ = databases
    with app.transaction() as session:
        session.add(user())
    column, value = next(iter(changes.items()))
    with pytest.raises(IntegrityError), app.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE users SET {column} = :value"), {"value": value}
        )


def test_normalized_uniqueness_and_sql_bypass_rejected(databases):
    app, _ = databases
    with app.transaction() as session:
        session.add(user(username=" Tester "))
    with pytest.raises(IntegrityError), app.transaction() as session:
        session.add(user(username="TESTER"))
        session.flush()
    with pytest.raises(IntegrityError), app.engine.begin() as connection:
        connection.execute(text("UPDATE users SET username = 'UPPERCASE'"))


@pytest.mark.parametrize(
    "table,column",
    [
        ("users", "username"),
        ("users", "role"),
        ("users", "created_at"),
        ("users", "updated_at"),
        ("tickets", "owner_id"),
        ("tickets", "status"),
        ("tickets", "created_at"),
        ("tickets", "updated_at"),
        ("comments", "ticket_id"),
        ("comments", "author_id"),
        ("comments", "created_at"),
    ],
)
def test_required_fields_cannot_be_null(databases, table, column):
    app, _ = databases
    seed_demo(app)
    with pytest.raises(IntegrityError), app.engine.begin() as connection:
        connection.execute(text(f"UPDATE {table} SET {column} = NULL"))


@pytest.mark.parametrize(
    "table, column, value",
    [
        ("tickets", "status", "invalid"),
        ("tickets", "title", None),
        ("tickets", "title", ""),
        ("tickets", "title", "x" * 201),
        ("tickets", "description", "x" * 10001),
        ("tickets", "description", None),
        ("tickets", "owner_id", 999999),
        ("comments", "content", None),
        ("comments", "content", ""),
        ("comments", "content", "x" * 5001),
        ("comments", "ticket_id", 999999),
        ("comments", "author_id", 999999),
    ],
)
def test_ticket_comment_constraints(databases, table, column, value):
    app, _ = databases
    seed_demo(app)
    with pytest.raises(IntegrityError), app.engine.begin() as connection:
        connection.execute(
            text(f"UPDATE {table} SET {column} = :value"), {"value": value}
        )


@pytest.mark.parametrize("loaded", [False, True])
def test_ticket_deletion_cascades_comments(databases, loaded):
    app, _ = databases
    seed_demo(app)
    with app.transaction() as session:
        ticket = session.get(Ticket, -2001)
        if loaded:
            assert len(ticket.comments) == 2
        session.delete(ticket)
    with app.transaction() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Comment)
                .where(Comment.ticket_id == -2001)
            )
            == 0
        )
        assert session.get(Ticket, -2002) is not None


@pytest.mark.parametrize("identifier", [-1001, -1003])
def test_referenced_user_cannot_be_deleted(databases, identifier):
    app, _ = databases
    seed_demo(app)
    with pytest.raises(IntegrityError), app.transaction() as session:
        session.delete(session.get(User, identifier))
        session.flush()


def test_seed_is_repeatable_and_hashes_fictitious_passwords(databases):
    app, _ = databases
    seed_demo(app)
    with app.transaction() as session:
        first = session.get(User, -1001).password_hash
    seed_demo(app)
    with app.transaction() as session:
        assert [
            session.scalar(select(func.count()).select_from(model))
            for model in (User, Ticket, Comment)
        ] == [3, 2, 3]
        assert session.get(User, -1001).password_hash == first
        assert first.startswith("$argon2id$")
        assert verify_password(first, "demo-Alice-only!")


@pytest.mark.parametrize(
    "collision", ["username", "id", "password", "ticket", "comment"]
)
def test_seed_collision_rolls_back_without_overwrite(databases, collision):
    app, _ = databases
    if collision in ("password", "ticket", "comment"):
        seed_demo(app)
    with app.transaction() as session:
        if collision == "username":
            session.add(user(username="bob"))
        elif collision == "id":
            session.add(user(id=-1002, username="different"))
        elif collision == "password":
            session.get(User, -1002).password_hash = "incompatible"
        elif collision == "ticket":
            session.get(Ticket, -2002).title = "Incompatible"
        else:
            session.get(Comment, -3003).content = "Incompatible"
    with app.engine.connect() as connection:
        before = [
            connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
            for table in ("users", "tickets", "comments")
        ]
    with pytest.raises(SeedCollision):
        seed_demo(app)
    with app.engine.connect() as connection:
        after = [
            connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
            for table in ("users", "tickets", "comments")
        ]
    assert after == before


def test_transaction_failure_has_no_partial_changes(databases):
    app, _ = databases
    with pytest.raises(RuntimeError), app.transaction() as session:
        session.add(user())
        session.flush()
        raise RuntimeError("Injected failure after SQL write")
    with app.transaction() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 0
        session.add(user())
    assert app.engine.pool.checkedout() == 0


def test_runtime_crud_and_updated_timestamp(databases):
    app, _ = databases
    seed_demo(app)
    with app.transaction() as session:
        session.get(Ticket, -2001).status = "closed"
        session.get(Comment, -3001).content = "Updated fictitious comment"
        session.get(User, -1001).active = False
    with app.transaction() as session:
        ticket = session.get(Ticket, -2001)
        assert ticket.status == "closed"
        assert ticket.updated_at > ticket.created_at
        assert session.get(User, -1001).active is False
        session.delete(ticket)


@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE forbidden_table (id integer)",
        "CREATE SCHEMA forbidden_schema",
        "CREATE TEMP TABLE forbidden_temp (id integer)",
        "ALTER TABLE users ADD COLUMN forbidden integer",
        "DROP TABLE comments",
        "TRUNCATE comments",
        "SELECT * FROM alembic_version",
        "SET ROLE vulnlab_migrate",
    ],
)
def test_runtime_ddl_and_migration_access_denied(databases, statement):
    app, _ = databases
    with pytest.raises(DBAPIError), app.engine.begin() as connection:
        connection.execute(text(statement))


def test_role_limits_and_future_grants(databases):
    app, migration = databases
    with migration.engine.begin() as connection:
        assert (
            connection.execute(text("SELECT current_user")).scalar()
            == "vulnlab_migrate"
        )
        assert (
            connection.execute(
                text(
                    "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
                )
            ).scalar()
            is False
        )
        connection.execute(
            text(
                "CREATE TABLE future_grant_test (id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, value text)"
            )
        )
    try:
        with app.engine.begin() as connection:
            connection.execute(
                text("INSERT INTO future_grant_test (value) VALUES ('fictitious')")
            )
            assert (
                connection.execute(text("SELECT value FROM future_grant_test")).scalar()
                == "fictitious"
            )
            connection.execute(text("UPDATE future_grant_test SET value = 'updated'"))
            connection.execute(text("DELETE FROM future_grant_test"))
    finally:
        with migration.engine.begin() as connection:
            connection.execute(text("DROP TABLE future_grant_test"))
