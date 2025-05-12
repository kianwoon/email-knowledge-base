"""fix_user_llm_config_user_id_type

Revision ID: 852c9266df12
Revises: 2d6f32b9bff8
Create Date: 2025-05-12 04:10:37.822175

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '852c9266df12'
down_revision: Union[str, None] = '2d6f32b9bff8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # First, create a temporary user_id_text column to store the UUID as string
    op.add_column('user_llm_configs', sa.Column('user_id_text', sa.String(), nullable=True))
    
    # Copy data from existing user_id column to the text column
    op.execute("UPDATE user_llm_configs SET user_id_text = user_id::text")
    
    # Drop the old column and rename the new one
    op.drop_column('user_llm_configs', 'user_id')
    op.alter_column('user_llm_configs', 'user_id_text', new_column_name='user_id')
    
    # Add constraints to the new column
    op.create_index(op.f('ix_user_llm_configs_user_id'), 'user_llm_configs', ['user_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    # This downgrade might lose data if the UUID format is not preserved
    # It's generally safer to not attempt to convert string back to UUID
    # But we'll provide a basic downgrade path
    
    # First, remove constraints
    op.drop_index(op.f('ix_user_llm_configs_user_id'), table_name='user_llm_configs')
    
    # Create temporary column
    op.add_column('user_llm_configs', sa.Column('user_id_uuid', UUID(as_uuid=True), nullable=True))
    
    # Try to convert valid UUIDs (this might fail if any are not valid UUID format)
    op.execute("UPDATE user_llm_configs SET user_id_uuid = user_id::uuid WHERE user_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'")
    
    # Drop old column and rename
    op.drop_column('user_llm_configs', 'user_id')
    op.alter_column('user_llm_configs', 'user_id_uuid', new_column_name='user_id')
    
    # Add constraints
    op.create_index(op.f('ix_user_llm_configs_user_id'), 'user_llm_configs', ['user_id'], unique=True)
