import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SQLAlchemyEnum, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, mapped_column, Mapped
from app.db.base_class import Base
from .azure_blob import AzureBlobConnection # Import the connection model

class AzureBlobSyncItem(Base):
    __tablename__ = 'azure_blob_sync_items'

    id = Column(Integer, primary_key=True, index=True)
    # Link to the specific Azure connection
    connection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('azure_blob_connections.id'), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)

    container_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    item_path: Mapped[str] = mapped_column(String, nullable=False, index=True) # Full path/prefix
    item_name: Mapped[str] = mapped_column(String, nullable=False) # Base name
    item_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'blob' or 'prefix'
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending', index=True) # e.g., pending, processing, completed, error

    # Relationships
    connection = relationship("AzureBlobConnection") # No back_populates needed if connection doesn't need to see items directly
    # user = relationship("UserDB") # Add if needed, depends on query patterns

    # Constraints
    __table_args__ = (
        UniqueConstraint('connection_id', 'item_path', name='uq_azure_connection_item_path'),
        Index('ix_azure_sync_items_user_status', 'user_id', 'status'),
        Index('ix_azure_sync_items_connection_status', 'connection_id', 'status')
    )

    def __repr__(self):
        return f"<AzureBlobSyncItem(id={self.id}, connection_id={self.connection_id}, path='{self.item_path}', status='{self.status}')>" 