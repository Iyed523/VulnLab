"""Reauthorize profile/admin operations inside their SQL transaction."""

from flask import abort
from sqlalchemy import func, select

from .auth_service import identity
from .models import User
from .web_controls import MAX_PAGE as MAX_PAGE
from .web_controls import PAGE_SIZE as PAGE_SIZE


def authorized_actor(session, actor, *, admin=False):
    record = session.scalar(select(User).where(User.id == actor.id).with_for_update())
    if (
        record is None
        or not record.active
        or record.session_version != actor.session_version
        or (admin and record.role != "admin")
    ):
        abort(403)
    return record


def profile(database, actor):
    with database.transaction() as session:
        return identity(authorized_actor(session, actor))


def require_admin(database, actor):
    with database.transaction() as session:
        authorized_actor(session, actor, admin=True)


def edit_profile(database, actor, display_name):
    with database.transaction() as session:
        record = authorized_actor(session, actor)
        record.display_name = display_name


def list_users(database, actor, page):
    with database.transaction() as session:
        authorized_actor(session, actor, admin=True)
        total = session.scalar(select(func.count()).select_from(User))
        rows = session.execute(
            select(User.id, User.username, User.display_name, User.role, User.active)
            .order_by(User.id)
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        ).all()
        return rows, total


def change_active(database, actor, identifier, active):
    with database.transaction() as session:
        authorized_actor(session, actor, admin=True)
        if not -(2**31) <= identifier < 2**31:
            abort(404)
        target = session.scalar(
            select(User).where(User.id == identifier).with_for_update()
        )
        if target is None:
            abort(404)
        if target.role != "user":
            abort(403)
        if target.active and not active:
            target.session_version += 1
        target.active = active
