"""ext_installs and ext_install_events: following installs before anyone signs in

Revision ID: d4f6b8c0e2a5
Revises: c3e5a7b9d2f4
Create Date: 2026-11-14 22:00:00.000000

Only adds new tables, so code from before this revision keeps working (deploys
never break on it). Written with IF NOT EXISTS so it can also run on a database
where the tables were created by hand ahead of the deploy (local testing shares
the production database); the revision is recorded when this runs on deploy.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4f6b8c0e2a5"
down_revision: Union[str, Sequence[str], None] = "c3e5a7b9d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE = [
    """
    CREATE TABLE IF NOT EXISTS ext_installs (
        id UUID PRIMARY KEY,
        install_id VARCHAR(36) NOT NULL UNIQUE,
        user_id UUID REFERENCES users (id) ON DELETE CASCADE,
        client_hash VARCHAR(64),
        version VARCHAR(20),
        browser VARCHAR(40),
        os VARCHAR(20),
        arch VARCHAR(20),
        language VARCHAR(20),
        timezone VARCHAR(50),
        automated BOOLEAN,
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        connected_at TIMESTAMPTZ,
        uninstalled_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ext_installs_created ON ext_installs (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_ext_installs_client_created"
    " ON ext_installs (client_hash, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_ext_installs_user ON ext_installs (user_id)",
    """
    CREATE TABLE IF NOT EXISTS ext_install_events (
        id UUID PRIMARY KEY,
        install_id VARCHAR(36) NOT NULL,
        name VARCHAR(40) NOT NULL,
        host VARCHAR(120),
        count INTEGER,
        client_id VARCHAR(36) NOT NULL,
        version VARCHAR(20),
        props JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ext_install_events_install"
    " ON ext_install_events (install_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_ext_install_events_name_created"
    " ON ext_install_events (name, created_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ext_install_events_client_id"
    " ON ext_install_events (client_id)",
]


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ext_install_events")
    op.execute("DROP TABLE IF EXISTS ext_installs")
