"""drop admin actions

HELD BACK: this file sits outside `versions/`, so `alembic upgrade head` does
not run it. The admin panel no longer writes an audit log, and that change ships
first; the table and its rows stay until this second step is chosen on purpose.
Dropping it deletes the rows for good (a downgrade brings back only an empty table).

To run it later:
  1. Back up the rows: pg_dump --table=admin_actions --data-only "$DATABASE_URL" > admin_actions.sql
  2. Move this file into `versions/` and set `down_revision` to the head at that
     time (`uv run alembic heads`), then `uv run alembic upgrade head`.

Revision ID: c9f3d5e7b1a2
Revises: b8e2c4f6a0d1
Create Date: 2026-10-27 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9f3d5e7b1a2"
down_revision: str | Sequence[str] | None = "b8e2c4f6a0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_admin_actions_created", table_name="admin_actions")
    op.drop_table("admin_actions")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "admin_actions",
        sa.Column("admin_email", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_actions_created", "admin_actions", ["created_at", "id"], unique=False)
