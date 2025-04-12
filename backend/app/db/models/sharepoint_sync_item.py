from sqlalchemy import Column, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import Mapped
from app.db.base_class import Base # Use the project's Base

class SharePointSyncItem(Base):
    """SQLAlchemy model for items selected by a user for SharePoint sync."""
    __tablename__ = 'sharepoint_sync_items'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True) # User identifier (e.g., email)
    item_type = Column(String, nullable=False) # 'file' or 'folder'
    sharepoint_item_id = Column(String, nullable=False, index=True)
    sharepoint_drive_id = Column(String, nullable=False)
    item_name = Column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending', index=True) # Added status field

    # Prevent adding the same item twice for the same user
    __table_args__ = (UniqueConstraint('user_id', 'sharepoint_item_id', name='uq_user_sharepoint_item'),
                      )

# Optional: Add specific indexes if query patterns demand it
# Index('ix_sharepoint_sync_items_user_id', 'user_id')
# Index('ix_sharepoint_sync_items_item_id', 'sharepoint_item_id') 