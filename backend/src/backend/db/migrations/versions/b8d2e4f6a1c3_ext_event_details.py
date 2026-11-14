"""ext_events: event id, extension version, session and properties

Revision ID: b8d2e4f6a1c3
Revises: a1b2c3d4e5f6
Create Date: 2026-11-14 18:00:00.000000

Only adds nullable columns and an index, so code from before this revision keeps
working against the new table (deploys never break on it).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b8d2e4f6a1c3"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Written so it can run on a table that already has these columns: they were added
# by hand ahead of the deploy (local testing shares the production database), and
# the revision is only recorded when this runs on deploy.
UPGRADE = [
    "ALTER TABLE ext_events ADD COLUMN IF NOT EXISTS client_id VARCHAR(36)",
    "ALTER TABLE ext_events ADD COLUMN IF NOT EXISTS version VARCHAR(20)",
    "ALTER TABLE ext_events ADD COLUMN IF NOT EXISTS session_id VARCHAR(36)",
    "ALTER TABLE ext_events ADD COLUMN IF NOT EXISTS props JSONB",
    # One row per event the extension sent, however often a batch is retried.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ext_events_client_id ON ext_events (client_id)"
    " WHERE client_id IS NOT NULL",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_ext_events_client_id")
    for column in ("props", "session_id", "version", "client_id"):
        op.execute(f"ALTER TABLE ext_events DROP COLUMN IF EXISTS {column}")
