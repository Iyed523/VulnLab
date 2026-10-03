"""Durable session revocation without replacing existing business records."""

import sqlalchemy as sa
from alembic import op

revision = "0002_session_version"
down_revision = "0001_data_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "session_version", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.create_check_constraint("session_version", "users", "session_version >= 0")


def downgrade():
    op.drop_constraint(op.f("ck_users_session_version"), "users", type_="check")
    op.drop_column("users", "session_version")
