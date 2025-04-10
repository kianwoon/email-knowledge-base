"""add_is_active_to_api_keys

Revision ID: 5ada9ead051f
Revises: 7e6667be8ba3
Create Date: 2025-04-10 15:40:54.261923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ada9ead051f'
down_revision: Union[str, None] = '7e6667be8ba3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_active column with default value True
    op.add_column('api_keys', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_active column
    op.drop_column('api_keys', 'is_active')
