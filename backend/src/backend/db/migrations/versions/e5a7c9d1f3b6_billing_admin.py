"""billing admin: editable plans, refunds and grants, and a log of admin actions

Revision ID: e5a7c9d1f3b6
Revises: d4f6b8c0e2a5
Create Date: 2026-11-14 23:00:00.000000

Only adds tables, nullable columns and one seed row, so code from before this
revision keeps working (deploys never break on it). Written so it can also run on
a database where these were created by hand ahead of the deploy (local testing
shares the production database); the revision is recorded when this runs on deploy.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5a7c9d1f3b6"
down_revision: Union[str, Sequence[str], None] = "d4f6b8c0e2a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE = [
    """
    CREATE TABLE IF NOT EXISTS billing_plans (
        plan VARCHAR(32) PRIMARY KEY,
        description VARCHAR(120) NOT NULL,
        amount INTEGER NOT NULL,
        currency VARCHAR(3) NOT NULL,
        days INTEGER NOT NULL,
        active BOOLEAN NOT NULL DEFAULT true,
        updated_by VARCHAR(320),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    # Today's price, so nothing changes for buyers when this runs.
    "INSERT INTO billing_plans (plan, description, amount, currency, days)"
    " VALUES ('pro_month', 'Rolesetu Pro, 1 month', 19900, 'INR', 30)"
    " ON CONFLICT (plan) DO NOTHING",
    "ALTER TABLE billing_orders ADD COLUMN IF NOT EXISTS days INTEGER",
    "ALTER TABLE billing_orders ADD COLUMN IF NOT EXISTS refunded_at TIMESTAMPTZ",
    "ALTER TABLE billing_orders ADD COLUMN IF NOT EXISTS refund_id VARCHAR(64)",
    "ALTER TABLE billing_orders ADD COLUMN IF NOT EXISTS note VARCHAR(200)",
    """
    CREATE TABLE IF NOT EXISTS billing_admin_actions (
        id UUID PRIMARY KEY,
        user_id UUID REFERENCES users (id) ON DELETE CASCADE,
        order_id UUID REFERENCES billing_orders (id) ON DELETE SET NULL,
        action VARCHAR(20) NOT NULL,
        admin_email VARCHAR(320) NOT NULL,
        note VARCHAR(200),
        amount INTEGER,
        days INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_billing_admin_actions_created"
    " ON billing_admin_actions (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_billing_admin_actions_user"
    " ON billing_admin_actions (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_billing_orders_status_created"
    " ON billing_orders (status, created_at)",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS billing_admin_actions")
    op.execute("DROP INDEX IF EXISTS ix_billing_orders_status_created")
    for column in ("note", "refund_id", "refunded_at", "days"):
        op.execute(f"ALTER TABLE billing_orders DROP COLUMN IF EXISTS {column}")
    op.execute("DROP TABLE IF EXISTS billing_plans")
