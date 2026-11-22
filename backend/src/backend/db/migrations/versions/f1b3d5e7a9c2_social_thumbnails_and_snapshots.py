"""social thumbnails and number history: a reel's thumbnail, and each reading of its numbers

Revision ID: f1b3d5e7a9c2
Revises: e8a0c2d4f6b9
Create Date: 2026-11-22 17:30:00.000000

Only adds a nullable column and a table, so code from before this revision keeps working.
Written with IF NOT EXISTS so it can be added by hand ahead of the deploy.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1b3d5e7a9c2"
down_revision: str | Sequence[str] | None = "e8a0c2d4f6b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = [
    "ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS thumbnail_url VARCHAR(2000)",
    """CREATE TABLE IF NOT EXISTS social_metric_snapshots (
        id UUID PRIMARY KEY,
        target_id UUID NOT NULL REFERENCES social_post_targets (id) ON DELETE CASCADE,
        taken_at TIMESTAMP WITH TIME ZONE NOT NULL,
        views INTEGER,
        likes INTEGER,
        comments INTEGER,
        shares INTEGER,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX IF NOT EXISTS ix_social_metric_snapshots_target_taken"
    " ON social_metric_snapshots (target_id, taken_at)",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS social_metric_snapshots")
    op.execute("ALTER TABLE social_posts DROP COLUMN IF EXISTS thumbnail_url")
