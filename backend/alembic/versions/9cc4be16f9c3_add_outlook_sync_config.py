"""add outlook sync config

Revision ID: 9cc4be16f9c3
Revises: 
Create Date: 2024-07-05 21:49:32.047782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9cc4be16f9c3'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the outlook_sync_config column to the users table
    op.add_column('users', sa.Column('outlook_sync_config', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the outlook_sync_config column from the users table
    op.drop_column('users', 'outlook_sync_config')
