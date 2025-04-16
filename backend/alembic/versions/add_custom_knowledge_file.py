"""
Revision ID: 20250416_1415_add_custom_knowledge_file
Revises: 
Create Date: 2025-04-16 14:15:00
"""
from alembic import op
import sqlalchemy as sa
# Import postgresql dialect explicitly for Enum
from sqlalchemy.dialects import postgresql 

# revision identifiers, used by Alembic.
revision = '20250416_1415_add_custom_knowledge_file'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Define the ENUM type object
    analysis_status_enum = postgresql.ENUM('pending', 'processing', 'completed', 'failed', name='analysisstatus', create_type=False)
    # Create the ENUM type in the database only if it doesn't exist
    analysis_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create the table
    op.create_table(
        'custom_knowledge_files',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_email', sa.String(), sa.ForeignKey('users.email'), index=True, nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('qdrant_collection', sa.String(), nullable=False),
        # Reference the ENUM type object here
        sa.Column('status', analysis_status_enum, nullable=False, server_default='pending'), 
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
    )

def downgrade():
    # Drop the table
    op.drop_table('custom_knowledge_files')
    
    # Define the ENUM type object again for dropping
    analysis_status_enum = postgresql.ENUM('pending', 'processing', 'completed', 'failed', name='analysisstatus', create_type=False)
    # Drop the ENUM type from the database only if it exists
    analysis_status_enum.drop(op.get_bind(), checkfirst=True)
