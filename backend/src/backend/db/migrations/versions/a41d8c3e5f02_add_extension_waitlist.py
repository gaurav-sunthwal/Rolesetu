"""add extension waitlist

Revision ID: a41d8c3e5f02
Revises: 7c2f1e9a4b6d
Create Date: 2026-10-14 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a41d8c3e5f02'
down_revision: Union[str, Sequence[str], None] = '7c2f1e9a4b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'extension_waitlist',
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('client_hash', sa.String(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_extension_waitlist_client_created', 'extension_waitlist', ['client_hash', 'created_at'], unique=False)
    op.create_index(op.f('ix_extension_waitlist_email'), 'extension_waitlist', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_extension_waitlist_email'), table_name='extension_waitlist')
    op.drop_index('ix_extension_waitlist_client_created', table_name='extension_waitlist')
    op.drop_table('extension_waitlist')
