from sqlalchemy import Column, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import mapped_column, Mapped
from app.db.base_class import Base # Use the project's Base

class S3SyncItem(Base):
    """SQLAlchemy model for S3 items selected by a user for sync."""
    __tablename__ = 's3_sync_items'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True) # User identifier (e.g., email)
    item_type = Column(String, nullable=False) # 'file' or 'prefix'
    s3_bucket = Column(String, nullable=False, index=True)
    s3_key = Column(String, nullable=False, index=True) # Full key of the object or prefix
    item_name = Column(String, nullable=False) # Base name of the file/prefix extracted from the key
    status: Mapped[str] = mapped_column(String(50), nullable=False, default='pending', index=True) # e.g., pending, processing, completed, failed

    # Prevent adding the same item (bucket + key) twice for the same user
    __table_args__ = (UniqueConstraint('user_id', 's3_bucket', 's3_key', name='uq_user_s3_item'),
                     Index('ix_s3_sync_items_user_status', 'user_id', 'status'), # Index for filtering by user and status
                      )

    def __repr__(self):
        return f"<S3SyncItem(id={self.id}, user='{self.user_id}', bucket='{self.s3_bucket}', key='{self.s3_key}', status='{self.status}')>" 