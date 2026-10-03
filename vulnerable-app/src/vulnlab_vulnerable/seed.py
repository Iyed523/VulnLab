"""Explicit fictitious fixtures, reserved negative IDs, no reset or overwrite."""

from sqlalchemy import select, text

from .models import Comment, Ticket, User
from .passwords import hash_password, verify_password

DEMO_USERS = (
    (-1001, "alice", "Alice", "user", "demo-Alice-only!"),
    (-1002, "bob", "Bob", "user", "demo-Bob-only!"),
    (-1003, "admin", "Admin fictif", "admin", "demo-Admin-only!"),
)
DEMO_TICKETS = (
    (-2001, -1001, "Alice demo ticket", "Fictitious private Alice data", "open"),
    (-2002, -1002, "Bob demo ticket", "Fictitious private Bob data", "in_progress"),
)
DEMO_COMMENTS = (
    (-3001, -2001, -1001, "Alice fictitious comment"),
    (-3002, -2001, -1003, "Admin fictitious response to Alice"),
    (-3003, -2002, -1002, "Bob fictitious comment"),
)


class SeedCollision(ValueError):
    pass


def ensure_record(session, model, identifier, fields):
    record = session.get(model, identifier)
    if record is None:
        record = model(id=identifier, **fields)
        session.add(record)
    elif any(getattr(record, key) != value for key, value in fields.items()):
        raise SeedCollision("Incompatible fictitious fixture; no data overwritten")
    return record


def seed_demo(database):
    with database.transaction() as session:
        # Serialize concurrent invocations of this explicit fixture command.
        session.execute(text("SELECT pg_advisory_xact_lock(505001)"))
        for identifier, username, display_name, role, password in DEMO_USERS:
            existing = session.scalar(select(User).where(User.username == username))
            if existing is not None and existing.id != identifier:
                raise SeedCollision(
                    "Fictitious username collision; no data overwritten"
                )
            fields = dict(
                username=username, display_name=display_name, role=role, active=True
            )
            record = session.get(User, identifier)
            if record is None:
                fields["password_hash"] = hash_password(password)
            elif not verify_password(record.password_hash, password):
                raise SeedCollision(
                    "Incompatible fictitious password; no data overwritten"
                )
            ensure_record(session, User, identifier, fields)
        session.flush()
        for identifier, owner_id, title, description, status in DEMO_TICKETS:
            ensure_record(
                session,
                Ticket,
                identifier,
                dict(
                    owner_id=owner_id,
                    title=title,
                    description=description,
                    status=status,
                ),
            )
        session.flush()
        for identifier, ticket_id, author_id, content in DEMO_COMMENTS:
            ensure_record(
                session,
                Comment,
                identifier,
                dict(ticket_id=ticket_id, author_id=author_id, content=content),
            )
