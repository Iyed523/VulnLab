"""Reference policy applied inside SQL transactions, including counts."""

from flask import abort
from sqlalchemy import delete, func, select

from .models import Comment, Ticket, User

PAGE_SIZE = 20
MAX_PAGE = 1000


def visible_tickets(actor):
    return (
        select(Ticket)
        if actor.role == "admin"
        else select(Ticket).where(Ticket.owner_id == actor.id)
    )


def authorized_ticket(session, actor, identifier, *, lock=False):
    if not -(2**31) <= identifier < 2**31:
        abort(404)
    query = visible_tickets(actor).where(Ticket.id == identifier)
    if lock:
        query = query.with_for_update()
    ticket = session.scalar(query)
    if ticket is None:
        abort(404)
    return ticket


def list_tickets(database, actor, page):
    with database.transaction() as session:
        query = visible_tickets(actor)
        total = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.scalars(
            query.order_by(Ticket.created_at.desc(), Ticket.id.desc())
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        ).all()
        return rows, total


def ticket_detail(database, actor, identifier, page):
    with database.transaction() as session:
        ticket = authorized_ticket(session, actor, identifier)
        total = session.scalar(
            select(func.count())
            .select_from(Comment)
            .where(Comment.ticket_id == ticket.id)
        )
        comments = session.execute(
            select(
                Comment.content,
                Comment.created_at,
                User.display_name.label("author_name"),
            )
            .join(User, User.id == Comment.author_id)
            .where(Comment.ticket_id == ticket.id)
            .order_by(Comment.created_at, Comment.id)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        ).all()
        return ticket, comments, total


def create_ticket(database, actor, title, description):
    with database.transaction() as session:
        ticket = Ticket(
            owner_id=actor.id, title=title, description=description, status="open"
        )
        session.add(ticket)
        session.flush()
        return ticket.id


def edit_ticket(database, actor, identifier, title, description, status):
    with database.transaction() as session:
        ticket = authorized_ticket(session, actor, identifier, lock=True)
        ticket.title, ticket.description, ticket.status = title, description, status


def delete_ticket(database, actor, identifier):
    with database.transaction() as session:
        ticket = authorized_ticket(session, actor, identifier, lock=True)
        # Database CASCADE owns comment deletion; do not load an unbounded relationship.
        session.execute(delete(Ticket).where(Ticket.id == ticket.id))


def add_comment(database, actor, identifier, content):
    with database.transaction() as session:
        ticket = authorized_ticket(session, actor, identifier, lock=True)
        session.add(Comment(ticket_id=ticket.id, author_id=actor.id, content=content))
