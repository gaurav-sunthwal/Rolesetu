"""credit_usage: AI credits spent per user per month; retire users' own Gemini keys

Revision ID: f9b1d3e5a7c2
Revises: e5a7c9d1f3b6
Create Date: 2026-11-15 00:30:00.000000

Adds a table (old code never reads it) and deletes the encrypted Gemini keys users
saved: the code from this release no longer reads them, and keeping a secret no
longer used is a risk with no benefit. The user_llm_keys table itself stays until a
later release, so code from before this one keeps working during the deploy.
Written with IF NOT EXISTS so the table can be created by hand ahead of the deploy
(local testing shares the production database).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f9b1d3e5a7c2"
down_revision: str | Sequence[str] | None = "e5a7c9d1f3b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS credit_usage (
        user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        period DATE NOT NULL,
        used INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, period)
    )
"""


def upgrade() -> None:
    op.execute(CREATE_TABLE)
    op.execute("DELETE FROM user_llm_keys")


def downgrade() -> None:
    # The deleted keys cannot come back; users would add them again.
    op.execute("DROP TABLE IF EXISTS credit_usage")
