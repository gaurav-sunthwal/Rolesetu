"""add match shares and social posting

Revision ID: c3e8a1f4d2b9
Revises: a9d3f5b7c1e2
Create Date: 2026-10-24 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3e8a1f4d2b9"
down_revision: str | Sequence[str] | None = "a9d3f5b7c1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[Any]]:
    return [
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
    ]


def upgrade() -> None:
    """Upgrade schema. New tables only, so code already running is unaffected."""
    op.create_table(
        "match_shares",
        sa.Column("slug", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("match_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=160), nullable=True),
        sa.Column("company", sa.String(length=160), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("matched", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_match_shares_user_created", "match_shares", ["user_id", "created_at"])
    op.create_index("ix_match_shares_match", "match_shares", ["match_id"], unique=True)

    op.create_table(
        "social_accounts",
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_by", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_social_accounts_platform_external",
        "social_accounts",
        ["platform", "external_id"],
        unique=True,
    )

    op.create_table(
        "social_posts",
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("approved_by", sa.String(length=320), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_social_posts_status_scheduled", "social_posts", ["status", "scheduled_at"])
    op.create_index("ix_social_posts_created", "social_posts", ["created_at", "id"])

    op.create_table(
        "social_post_targets",
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("external_url", sa.String(length=2000), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["post_id"], ["social_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_social_post_targets_post", "social_post_targets", ["post_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_social_post_targets_post", table_name="social_post_targets")
    op.drop_table("social_post_targets")
    op.drop_index("ix_social_posts_created", table_name="social_posts")
    op.drop_index("ix_social_posts_status_scheduled", table_name="social_posts")
    op.drop_table("social_posts")
    op.drop_index("ix_social_accounts_platform_external", table_name="social_accounts")
    op.drop_table("social_accounts")
    op.drop_index("ix_match_shares_match", table_name="match_shares")
    op.drop_index("ix_match_shares_user_created", table_name="match_shares")
    op.drop_table("match_shares")
