"""social reels, YouTube and post numbers: video posts, YouTube texts, and views/watch time

Revision ID: e8a0c2d4f6b9
Revises: c4e6a8b0d2f3
Create Date: 2026-11-22 16:00:00.000000

Only adds nullable columns and an index, so code from before this revision keeps working.
Written with IF NOT EXISTS so it can be added by hand ahead of the deploy.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e8a0c2d4f6b9"
down_revision: str | Sequence[str] | None = "c4e6a8b0d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = [
    "ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS followers INTEGER",
    "ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS video_key VARCHAR(200)",
    "ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS youtube_title VARCHAR(100)",
    "ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS youtube_description TEXT",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS external_id VARCHAR(100)",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS views INTEGER",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS reach INTEGER",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS likes INTEGER",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS comments INTEGER",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS shares INTEGER",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS saves INTEGER",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS avg_watch_ms INTEGER",
    "ALTER TABLE social_post_targets ADD COLUMN IF NOT EXISTS metrics_at TIMESTAMP WITH TIME ZONE",
    "CREATE INDEX IF NOT EXISTS ix_social_post_targets_status_posted"
    " ON social_post_targets (status, posted_at)",
]

_COLUMNS = {
    "social_accounts": ["followers"],
    "social_posts": ["video_key", "youtube_title", "youtube_description"],
    "social_post_targets": [
        "external_id",
        "views",
        "reach",
        "likes",
        "comments",
        "shares",
        "saves",
        "avg_watch_ms",
        "metrics_at",
    ],
}


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_social_post_targets_status_posted")
    for table, columns in _COLUMNS.items():
        for column in columns:
            op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")
