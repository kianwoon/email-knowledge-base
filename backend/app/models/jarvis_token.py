from sqlalchemy import Column, Integer, String, DateTime, Boolean, LargeBinary, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID # Import UUID type
from sqlalchemy.sql import func
from ..db.base_class import Base
from sqlalchemy.orm import relationship

class JarvisExternalToken(Base):
    __tablename__ = 'jarvis_external_tokens'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True) # CHANGED: Use UUID type
    token_nickname = Column(String(255), nullable=False)
    encrypted_token_value = Column(LargeBinary, nullable=False) # For BYTEA
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    is_valid = Column(Boolean, default=True, nullable=False, index=True)

    # Optional: Define relationship back to User model if you have one
    # owner = relationship("User", back_populates="jarvis_tokens") 

    # Optional: Add unique constraint at the model level if not done in SQL
    # Ensure column names in constraint are correct
    __table_args__ = (UniqueConstraint('user_id', 'token_nickname', name='uq_user_token_nickname'),)

    def __repr__(self):
        return f"<JarvisExternalToken(id={self.id}, user_id={self.user_id}, nickname='{self.token_nickname}', is_valid={self.is_valid})>" 