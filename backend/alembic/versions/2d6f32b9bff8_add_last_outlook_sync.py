"""add_last_outlook_sync

Revision ID: 2d6f32b9bff8
Revises: 9cc4be16f9c3
Create Date: 2023-07-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2d6f32b9bff8'
down_revision: Union[str, None] = '9cc4be16f9c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_outlook_sync column to users table."""
    op.add_column('users', sa.Column('last_outlook_sync', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove last_outlook_sync column from users table."""
    op.drop_column('users', 'last_outlook_sync')
