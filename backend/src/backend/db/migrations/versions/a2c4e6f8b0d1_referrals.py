"""referrals: invite codes, and the friends who joined through them

Revision ID: a2c4e6f8b0d1
Revises: f9b1d3e5a7c2
Create Date: 2026-11-15 02:00:00.000000

Only adds new tables, so code from before this revision keeps working. Written
with IF NOT EXISTS so the tables can be created by hand ahead of the deploy (local
testing shares the production database).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a2c4e6f8b0d1"
down_revision: str | Sequence[str] | None = "f9b1d3e5a7c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = [
    """
    CREATE TABLE IF NOT EXISTS referral_codes (
        user_id UUID PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
        code VARCHAR(12) NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS referrals (
        id UUID PRIMARY KEY,
        referrer_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        referred_id UUID NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
        qualified_at TIMESTAMPTZ,
        order_id UUID REFERENCES billing_orders (id) ON DELETE SET NULL,
        used_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CHECK (referrer_id <> referred_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_referrals_referrer_created"
    " ON referrals (referrer_id, created_at)",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS referrals")
    op.execute("DROP TABLE IF EXISTS referral_codes")
