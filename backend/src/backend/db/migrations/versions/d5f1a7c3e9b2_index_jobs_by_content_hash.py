"""index jobs by content hash and job id, for reusing a job's reading and result

Revision ID: d5f1a7c3e9b2
Revises: c3e8a1f4d2b9
Create Date: 2026-10-27 12:00:00.000000

Built concurrently, so writes to jobs are not blocked while it is made. The
code works without it (the lookup is just slower), so it can be applied any
time after the deploy.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f1a7c3e9b2"
down_revision: str | Sequence[str] | None = "c3e8a1f4d2b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_jobs_content_hash",
            "jobs",
            ["content_hash"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        # The job's id from its link ("linkedin:4460038564"), kept in job_json.
        op.create_index(
            "ix_jobs_job_key",
            "jobs",
            [sa.text("(job_json ->> 'job_key')")],
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_jobs_job_key",
            table_name="jobs",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_jobs_content_hash",
            table_name="jobs",
            postgresql_concurrently=True,
            if_exists=True,
        )
