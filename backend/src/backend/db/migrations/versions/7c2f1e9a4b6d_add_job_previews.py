"""add job previews

Revision ID: 7c2f1e9a4b6d
Revises: 216d590fc5c7
Create Date: 2026-10-13 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7c2f1e9a4b6d'
down_revision: Union[str, Sequence[str], None] = '216d590fc5c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'job_previews',
        sa.Column('url_hash', sa.String(), nullable=False),
        sa.Column('client_hash', sa.String(), nullable=False),
        sa.Column('reader', sa.String(), nullable=True),
        sa.Column('page', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_job_previews_client_created', 'job_previews', ['client_hash', 'created_at'], unique=False)
    op.create_index('ix_job_previews_created', 'job_previews', ['created_at'], unique=False)
    op.create_index('ix_job_previews_url_created', 'job_previews', ['url_hash', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_job_previews_url_created', table_name='job_previews')
    op.drop_index('ix_job_previews_created', table_name='job_previews')
    op.drop_index('ix_job_previews_client_created', table_name='job_previews')
    op.drop_table('job_previews')
