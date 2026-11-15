"""resume_files.ai_status: the AI's understanding is added after the upload answers

Revision ID: c4e6a8b0d2f3
Revises: b3d5f7a9c1e2
Create Date: 2026-11-15 17:00:00.000000

Only adds a nullable column, so code from before this revision keeps working.
Written with IF NOT EXISTS so it can be added by hand ahead of the deploy.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4e6a8b0d2f3"
down_revision: str | Sequence[str] | None = "b3d5f7a9c1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = ["ALTER TABLE resume_files ADD COLUMN IF NOT EXISTS ai_status VARCHAR(16)"]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("ALTER TABLE resume_files DROP COLUMN IF EXISTS ai_status")
