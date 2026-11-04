"""add ai calls

Revision ID: b8e2c4f6a0d1
Revises: d5f1a7c3e9b2
Create Date: 2026-10-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e2c4f6a0d1"
down_revision: str | Sequence[str] | None = "d5f1a7c3e9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ai_calls",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("own_key", sa.Boolean(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_calls_created", "ai_calls", ["created_at", "id"], unique=False)
    op.create_index(
        "ix_ai_calls_source_created", "ai_calls", ["source", "created_at"], unique=False
    )
    op.create_index("ix_ai_calls_user_created", "ai_calls", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ai_calls_user_created", table_name="ai_calls")
    op.drop_index("ix_ai_calls_source_created", table_name="ai_calls")
    op.drop_index("ix_ai_calls_created", table_name="ai_calls")
    op.drop_table("ai_calls")
