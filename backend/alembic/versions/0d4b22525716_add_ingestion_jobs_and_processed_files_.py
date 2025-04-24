"""Add ingestion_jobs and processed_files tables

Revision ID: 0d4b22525716
Revises: 2f9f6d2285bd
Create Date: 2025-04-24 12:22:22.780850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0d4b22525716'
down_revision: Union[str, None] = '2f9f6d2285bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands manually created based on models ###
    op.create_table('ingestion_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('job_details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('celery_task_id', sa.String(length=36), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ingestion_jobs'))
    )
    op.create_index(op.f('ix_ingestion_jobs_celery_task_id'), 'ingestion_jobs', ['celery_task_id'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_id'), 'ingestion_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_source_type'), 'ingestion_jobs', ['source_type'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_status'), 'ingestion_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_ingestion_jobs_user_id'), 'ingestion_jobs', ['user_id'], unique=False)
    op.create_index('ix_ingestion_jobs_user_status', 'ingestion_jobs', ['user_id', 'status'], unique=False)

    op.create_table('processed_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ingestion_job_id', sa.Integer(), nullable=False),
        sa.Column('owner_email', sa.String(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('source_identifier', sa.Text(), nullable=False),
        sa.Column('original_filename', sa.String(length=1024), nullable=False),
        sa.Column('r2_object_key', sa.Text(), nullable=False),
        sa.Column('content_type', sa.String(length=255), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending_analysis'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ingestion_job_id'], ['ingestion_jobs.id'], name=op.f('fk_processed_files_ingestion_job_id_ingestion_jobs')),
        sa.ForeignKeyConstraint(['owner_email'], ['users.email'], name=op.f('fk_processed_files_owner_email_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_processed_files')),
        sa.UniqueConstraint('r2_object_key', name=op.f('uq_processed_files_r2_object_key'))
    )
    op.create_index(op.f('ix_processed_files_id'), 'processed_files', ['id'], unique=False)
    op.create_index(op.f('ix_processed_files_ingestion_job_id'), 'processed_files', ['ingestion_job_id'], unique=False)
    op.create_index(op.f('ix_processed_files_owner_email'), 'processed_files', ['owner_email'], unique=False)
    op.create_index('ix_processed_files_owner_status', 'processed_files', ['owner_email', 'status'], unique=False)
    op.create_index(op.f('ix_processed_files_r2_object_key'), 'processed_files', ['r2_object_key'], unique=True)
    op.create_index(op.f('ix_processed_files_source_identifier'), 'processed_files', ['source_identifier'], unique=False)
    op.create_index(op.f('ix_processed_files_source_type'), 'processed_files', ['source_type'], unique=False)
    op.create_index(op.f('ix_processed_files_status'), 'processed_files', ['status'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands manually created based on models ###
    op.drop_index(op.f('ix_processed_files_status'), table_name='processed_files')
    op.drop_index(op.f('ix_processed_files_source_type'), table_name='processed_files')
    op.drop_index(op.f('ix_processed_files_source_identifier'), table_name='processed_files')
    op.drop_index(op.f('ix_processed_files_r2_object_key'), table_name='processed_files')
    op.drop_index('ix_processed_files_owner_status', table_name='processed_files')
    op.drop_index(op.f('ix_processed_files_owner_email'), table_name='processed_files')
    op.drop_index(op.f('ix_processed_files_ingestion_job_id'), table_name='processed_files')
    op.drop_index(op.f('ix_processed_files_id'), table_name='processed_files')
    op.drop_table('processed_files')

    op.drop_index('ix_ingestion_jobs_user_status', table_name='ingestion_jobs')
    op.drop_index(op.f('ix_ingestion_jobs_user_id'), table_name='ingestion_jobs')
    op.drop_index(op.f('ix_ingestion_jobs_status'), table_name='ingestion_jobs')
    op.drop_index(op.f('ix_ingestion_jobs_source_type'), table_name='ingestion_jobs')
    op.drop_index(op.f('ix_ingestion_jobs_id'), table_name='ingestion_jobs')
    op.drop_index(op.f('ix_ingestion_jobs_celery_task_id'), table_name='ingestion_jobs')
    op.drop_table('ingestion_jobs')
    # ### end Alembic commands ###
