"""add ext_events table for extension usage analytics

Revision ID: a1b2c3d4e5f6
Revises: f2b4d6a8c0e1
Create Date: 2026-11-07 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = ("f2b4d6a8c0e1", "f7a2b8c4d1e0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ext_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("host", sa.String(120), nullable=True),
        sa.Column("count", sa.Integer(), nullable=True),
    )
    op.create_index("ix_ext_events_user_created", "ext_events", ["user_id", "created_at", "id"])
    op.create_index("ix_ext_events_name_created", "ext_events", ["name", "created_at"])
    op.create_index("ix_ext_events_host_created", "ext_events", ["host", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ext_events_host_created")
    op.drop_index("ix_ext_events_name_created")
    op.drop_index("ix_ext_events_user_created")
    op.drop_table("ext_events")
