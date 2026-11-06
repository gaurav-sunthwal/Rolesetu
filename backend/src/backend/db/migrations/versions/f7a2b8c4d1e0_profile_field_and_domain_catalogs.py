"""profile field and domain skill catalogs

Revision ID: f7a2b8c4d1e0
Revises: d1a4b6c8e0f3
Create Date: 2026-11-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f7a2b8c4d1e0"
down_revision: Union[str, Sequence[str], None] = "d1a4b6c8e0f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("field_key", sa.String(length=32), nullable=True))
    op.add_column("profiles", sa.Column("scope_summary", sa.String(length=500), nullable=True))
    op.add_column(
        "profiles", sa.Column("inferred_field_key", sa.String(length=32), nullable=True)
    )
    op.create_table(
        "domain_skill_catalogs",
        sa.Column("field_key", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("catalog_text", sa.Text(), nullable=False),
        sa.Column(
            "core_skill_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("field_key", "version"),
    )


def downgrade() -> None:
    op.drop_table("domain_skill_catalogs")
    op.drop_column("profiles", "inferred_field_key")
    op.drop_column("profiles", "scope_summary")
    op.drop_column("profiles", "field_key")
