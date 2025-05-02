# backend/app/models/external_audit_log.py
import logging
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import JSONB # Use if DB is PostgreSQL and contains JSON

logger = logging.getLogger(__name__)

# Define a base specific to this external model to avoid Alembic detection.
# If connecting to the same DB, this might not be strictly necessary,
# but provides clarity that this table is not managed by app migrations.
ExternalBase = declarative_base()

class ExternalAuditLog(ExternalBase):
    """SQLAlchemy model representing the externally managed audit_logs table."""
    __tablename__ = 'audit_logs'

    # Explicitly prevent Alembic from managing this table if it shares the same metadata
    # This might be needed if not using a separate ExternalBase/metadata
    # __table_args__ = {'info': {'managed_by_app': False}}

    # Define columns based on inferred schema from sample and old migration
    id = Column(Integer, primary_key=True)
    token_id = Column(Integer, nullable=False, index=True) # FK to internal tokens.id
    resource_id = Column(String, nullable=True) # e.g., collection name used
    action_type = Column(String, nullable=True) # e.g., shared_knowledge_search
    query_text = Column(Text, nullable=False) # From the NotNullViolation error
    filter_data = Column(Text, nullable=True) # Using Text for broad compatibility
    result_count = Column(Integer, nullable=True)
    response_data = Column(Text, nullable=True) # Using Text for broad compatibility
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<ExternalAuditLog(id={self.id}, token_id={self.token_id}, action='{self.action_type}', timestamp='{self.created_at}')>" 