"""merge heads

Revision ID: 2f9f6d2285bd
Revises: 683446c2aab8, 20250416_1415_add_custom_knowledge_file
Create Date: 2025-04-16 14:36:18.464953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f9f6d2285bd'
down_revision: Union[str, None] = ('683446c2aab8', '20250416_1415_add_custom_knowledge_file')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
