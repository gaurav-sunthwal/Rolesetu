"""autopay subscriptions, Razorpay plans per price, and payment funnel events

Revision ID: b3d5f7a9c1e2
Revises: a2c4e6f8b0d1
Create Date: 2026-11-15 03:00:00.000000

Only adds new tables, so code from before this revision keeps working. Written with
IF NOT EXISTS so the tables can be created by hand ahead of the deploy (local testing
shares the production database).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b3d5f7a9c1e2"
down_revision: str | Sequence[str] | None = "a2c4e6f8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE = [
    """
    CREATE TABLE IF NOT EXISTS billing_razorpay_plans (
        razorpay_plan_id VARCHAR(64) PRIMARY KEY,
        amount INTEGER NOT NULL,
        currency VARCHAR(3) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_razorpay_plan_price UNIQUE (amount, currency)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS billing_subscriptions (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        razorpay_subscription_id VARCHAR(64) NOT NULL UNIQUE,
        razorpay_plan_id VARCHAR(64) NOT NULL,
        amount INTEGER NOT NULL,
        currency VARCHAR(3) NOT NULL,
        days INTEGER NOT NULL,
        status VARCHAR(16) NOT NULL,
        offer_id VARCHAR(32),
        referral_id UUID REFERENCES referrals (id) ON DELETE SET NULL,
        start_at TIMESTAMPTZ,
        current_start TIMESTAMPTZ,
        current_end TIMESTAMPTZ,
        charge_at TIMESTAMPTZ,
        cancel_at_cycle_end BOOLEAN NOT NULL DEFAULT false,
        ended_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_billing_subscriptions_user_created"
    " ON billing_subscriptions (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_billing_subscriptions_status_updated"
    " ON billing_subscriptions (status, updated_at)",
    """
    CREATE TABLE IF NOT EXISTS billing_funnel_events (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        attempt_id UUID,
        step VARCHAR(32) NOT NULL,
        source VARCHAR(8) NOT NULL,
        detail JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_billing_funnel_created ON billing_funnel_events (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_billing_funnel_user_created"
    " ON billing_funnel_events (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_billing_funnel_step_created"
    " ON billing_funnel_events (step, created_at)",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for table in ("billing_funnel_events", "billing_subscriptions", "billing_razorpay_plans"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
