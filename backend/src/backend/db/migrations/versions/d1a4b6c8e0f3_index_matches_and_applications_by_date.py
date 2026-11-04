"""index matches and applications by date

For the admin panel's lists of everyone's job checks and applications, which
are ordered newest first across all users.

Revision ID: d1a4b6c8e0f3
Revises: b8e2c4f6a0d1
Create Date: 2026-10-27 15:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a4b6c8e0f3"
down_revision: str | Sequence[str] | None = "b8e2c4f6a0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_matches_created", "matches", ["created_at", "id"], unique=False)
    op.create_index("ix_applications_created", "applications", ["created_at", "id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_applications_created", table_name="applications")
    op.drop_index("ix_matches_created", table_name="matches")
