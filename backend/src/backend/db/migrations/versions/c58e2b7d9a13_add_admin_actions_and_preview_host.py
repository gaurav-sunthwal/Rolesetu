"""add admin actions and preview host

Revision ID: c58e2b7d9a13
Revises: a41d8c3e5f02
Create Date: 2026-10-14 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c58e2b7d9a13'
down_revision: Union[str, Sequence[str], None] = 'a41d8c3e5f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'admin_actions',
        sa.Column('admin_email', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('target_type', sa.String(), nullable=False),
        sa.Column('target_id', sa.String(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_admin_actions_created', 'admin_actions', ['created_at', 'id'], unique=False)
    op.add_column('job_previews', sa.Column('host', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('job_previews', 'host')
    op.drop_index('ix_admin_actions_created', table_name='admin_actions')
    op.drop_table('admin_actions')
