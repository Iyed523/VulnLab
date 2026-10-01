"""Persistence constraints, not authorization checks."""

import re
import unicodedata
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    validates,
)


def normalize_username(value):
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,31}", normalized, flags=re.ASCII):
        raise ValueError("Username must normalize to 3-32 ASCII account characters")
    return normalized


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="role"),
        CheckConstraint("username ~ '^[a-z0-9][a-z0-9_.-]{2,31}$'", name="username"),
        CheckConstraint("length(display_name) BETWEEN 1 AND 100", name="display_name"),
        CheckConstraint(
            "length(password_hash) BETWEEN 1 AND 255", name="password_hash"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(5), server_default="user")
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    @validates("username")
    def normalized_username(self, key, value):
        return normalize_username(value)


class Ticket(Timestamps, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_progress', 'closed')", name="status"),
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="title"),
        CheckConstraint("length(description) BETWEEN 1 AND 10000", name="description"),
    )
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(11), server_default="open")
    owner: Mapped[User] = relationship()
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", passive_deletes=True
    )


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint("length(content) BETWEEN 1 AND 5000", name="content"),
    )
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ticket: Mapped[Ticket] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()
