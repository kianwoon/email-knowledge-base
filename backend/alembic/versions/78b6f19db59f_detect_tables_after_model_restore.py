"""Detect tables after model restore

Revision ID: 78b6f19db59f
Revises: 9770346a8066
Create Date: 2025-04-13 22:48:28.056488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78b6f19db59f'
down_revision: Union[str, None] = '9770346a8066'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('aws_credentials',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_email', sa.String(), nullable=False),
    sa.Column('role_arn', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_email', name='uq_user_aws_credential')
    )
    op.create_index(op.f('ix_aws_credentials_id'), 'aws_credentials', ['id'], unique=False)
    op.create_index(op.f('ix_aws_credentials_user_email'), 'aws_credentials', ['user_email'], unique=True)
    op.create_table('s3_sync_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('item_type', sa.String(), nullable=False),
    sa.Column('s3_bucket', sa.String(), nullable=False),
    sa.Column('s3_key', sa.String(), nullable=False),
    sa.Column('item_name', sa.String(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 's3_bucket', 's3_key', name='uq_user_s3_item')
    )
    op.create_index(op.f('ix_s3_sync_items_id'), 's3_sync_items', ['id'], unique=False)
    op.create_index(op.f('ix_s3_sync_items_s3_bucket'), 's3_sync_items', ['s3_bucket'], unique=False)
    op.create_index(op.f('ix_s3_sync_items_s3_key'), 's3_sync_items', ['s3_key'], unique=False)
    op.create_index(op.f('ix_s3_sync_items_status'), 's3_sync_items', ['status'], unique=False)
    op.create_index(op.f('ix_s3_sync_items_user_id'), 's3_sync_items', ['user_id'], unique=False)
    op.create_index('ix_s3_sync_items_user_status', 's3_sync_items', ['user_id', 'status'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_s3_sync_items_user_status', table_name='s3_sync_items')
    op.drop_index(op.f('ix_s3_sync_items_user_id'), table_name='s3_sync_items')
    op.drop_index(op.f('ix_s3_sync_items_status'), table_name='s3_sync_items')
    op.drop_index(op.f('ix_s3_sync_items_s3_key'), table_name='s3_sync_items')
    op.drop_index(op.f('ix_s3_sync_items_s3_bucket'), table_name='s3_sync_items')
    op.drop_index(op.f('ix_s3_sync_items_id'), table_name='s3_sync_items')
    op.drop_table('s3_sync_items')
    op.drop_index(op.f('ix_aws_credentials_user_email'), table_name='aws_credentials')
    op.drop_index(op.f('ix_aws_credentials_id'), table_name='aws_credentials')
    op.drop_table('aws_credentials')
    # ### end Alembic commands ###
