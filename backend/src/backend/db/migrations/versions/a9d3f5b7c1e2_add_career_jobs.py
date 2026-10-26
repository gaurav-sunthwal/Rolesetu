"""add career jobs

Revision ID: a9d3f5b7c1e2
Revises: f2b4d6a8c0e1
Create Date: 2026-10-18 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9d3f5b7c1e2"
down_revision: str | Sequence[str] | None = "f2b4d6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "career_companies",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("added", sa.Boolean(), nullable=False),
        sa.Column("added_by", sa.UUID(), nullable=True),
        sa.Column("error", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("slug"),
    )
    op.create_index(
        "ix_career_companies_added_by_created", "career_companies", ["added_by", "created_at"]
    )
    op.create_table(
        "career_jobs",
        sa.Column("id", sa.String(length=300), nullable=False),
        sa.Column("company_slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=False),
        sa.Column("places", postgresql.ARRAY(sa.String(length=80)), nullable=False),
        sa.Column("posted_on", sa.Date(), nullable=True),
        sa.Column("first_seen", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("min_years", sa.Float(), nullable=True),
        sa.Column("max_years", sa.Float(), nullable=True),
        sa.Column("experience_source", sa.String(length=40), nullable=True),
        sa.Column("experience_quote", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["company_slug"], ["career_companies.slug"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_career_jobs_company_slug", "career_jobs", ["company_slug"])
    op.create_table(
        "career_collector",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # The one row the collector works from.
    op.execute("INSERT INTO career_collector (id, version) VALUES (1, 0)")


def downgrade() -> None:
    op.drop_table("career_collector")
    op.drop_index("ix_career_jobs_company_slug", table_name="career_jobs")
    op.drop_table("career_jobs")
    op.drop_index("ix_career_companies_added_by_created", table_name="career_companies")
    op.drop_table("career_companies")
