"""billing_orders: Razorpay orders, and the months of Pro they paid for

Revision ID: c3e5a7b9d2f4
Revises: b8d2e4f6a1c3
Create Date: 2026-11-14 21:00:00.000000

Only adds a new table, so code from before this revision keeps working (deploys
never break on it). Written with IF NOT EXISTS so it can also run on a database
where the table was created by hand ahead of the deploy (local testing shares the
production database); the revision is recorded when this runs on deploy.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c3e5a7b9d2f4"
down_revision: Union[str, Sequence[str], None] = "b8d2e4f6a1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE = [
    """
    CREATE TABLE IF NOT EXISTS billing_orders (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
        razorpay_order_id VARCHAR(64) NOT NULL UNIQUE,
        razorpay_payment_id VARCHAR(64) UNIQUE,
        plan VARCHAR(32) NOT NULL,
        amount INTEGER NOT NULL,
        currency VARCHAR(3) NOT NULL,
        status VARCHAR(16) NOT NULL,
        paid_at TIMESTAMPTZ,
        pro_starts_at TIMESTAMPTZ,
        pro_ends_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_billing_orders_user_created"
    " ON billing_orders (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_billing_orders_user_paid_ends"
    " ON billing_orders (user_id, pro_ends_at) WHERE status = 'paid'",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS billing_orders")
