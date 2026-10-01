"""Users, private tickets and comments; no authorization flow."""

import sqlalchemy as sa
from alembic import op

revision = "0001_data_foundation"
down_revision = None
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(5), server_default="user", nullable=False),
        sa.Column(
            "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        *timestamps(),
        sa.UniqueConstraint("username"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="role"),
        sa.CheckConstraint("username ~ '^[a-z0-9][a-z0-9_.-]{2,31}$'", name="username"),
        sa.CheckConstraint(
            "length(display_name) BETWEEN 1 AND 100", name="display_name"
        ),
        sa.CheckConstraint(
            "length(password_hash) BETWEEN 1 AND 255", name="password_hash"
        ),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(11), server_default="open", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'closed')", name="status"
        ),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 200", name="title"),
        sa.CheckConstraint(
            "length(description) BETWEEN 1 AND 10000", name="description"
        ),
    )
    op.create_index("ix_tickets_owner_id", "tickets", ["owner_id"])
    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.Integer(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 5000", name="content"),
    )
    op.create_index("ix_comments_ticket_id", "comments", ["ticket_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])
    # This revision grants only the business tables, never alembic_version.
    for table in ("users", "tickets", "comments"):
        op.execute(
            sa.text(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO vulnlab_app"
            )
        )
        op.execute(
            sa.text(f"GRANT USAGE, SELECT ON SEQUENCE {table}_id_seq TO vulnlab_app")
        )
    op.execute(sa.text("REVOKE ALL ON TABLE alembic_version FROM vulnlab_app"))


def downgrade():
    # Destructive: exercised only by tests on their explicitly ephemeral database.
    op.drop_table("comments")
    op.drop_table("tickets")
    op.drop_table("users")
