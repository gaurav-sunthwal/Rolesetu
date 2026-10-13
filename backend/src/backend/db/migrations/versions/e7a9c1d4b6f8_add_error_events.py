"""add error events

Revision ID: e7a9c1d4b6f8
Revises: c58e2b7d9a13
Create Date: 2026-10-14 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7a9c1d4b6f8'
down_revision: Union[str, Sequence[str], None] = 'c58e2b7d9a13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'error_events',
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('level', sa.String(), nullable=False),
        sa.Column('fingerprint', sa.String(), nullable=False),
        sa.Column('route', sa.String(), nullable=True),
        sa.Column('method', sa.String(), nullable=True),
        sa.Column('status', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('stack', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_error_events_created', 'error_events', ['created_at'], unique=False)
    op.create_index('ix_error_events_fingerprint_created', 'error_events', ['fingerprint', 'created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_error_events_fingerprint_created', table_name='error_events')
    op.drop_index('ix_error_events_created', table_name='error_events')
    op.drop_table('error_events')
