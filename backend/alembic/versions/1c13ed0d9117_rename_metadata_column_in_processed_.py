"""Rename metadata column in processed_files to additional_data

Revision ID: 1c13ed0d9117
Revises: 0d4b22525716
Create Date: 2025-04-24 13:02:27.652843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1c13ed0d9117'
down_revision: Union[str, None] = '0d4b22525716'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands manually corrected ###
    op.alter_column('processed_files', 'metadata', new_column_name='additional_data', existing_type=postgresql.JSONB(astext_type=sa.Text()), existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands manually corrected ###
    op.alter_column('processed_files', 'additional_data', new_column_name='metadata', existing_type=postgresql.JSONB(astext_type=sa.Text()), existing_nullable=True)
    # ### end Alembic commands ###
