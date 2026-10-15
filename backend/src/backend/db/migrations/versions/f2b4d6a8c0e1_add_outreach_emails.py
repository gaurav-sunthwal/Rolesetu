"""add outreach emails

Revision ID: f2b4d6a8c0e1
Revises: e7a9c1d4b6f8
Create Date: 2026-10-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2b4d6a8c0e1'
down_revision: Union[str, Sequence[str], None] = 'e7a9c1d4b6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'outreach_emails',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('admin_email', sa.String(), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outreach_emails_user_created', 'outreach_emails', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_outreach_emails_user_created', table_name='outreach_emails')
    op.drop_table('outreach_emails')
