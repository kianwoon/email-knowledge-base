import typing
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped
from app.db.base_class import Base

if typing.TYPE_CHECKING:
    from app.models.user import UserDB  # Import for type hinting only

class AwsCredential(Base):
    """SQLAlchemy model for storing AWS credentials (Role ARN) per user."""
    __tablename__ = 'aws_credentials'

    id = Column(Integer, primary_key=True, index=True)
    # Link to users table via email (the primary key of UserDB)
    user_email = Column(String, ForeignKey("users.email"), unique=True, index=True, nullable=False) 
    role_arn = Column(String, nullable=False)

    # Define the relationship with UserDB
    user = relationship("UserDB", back_populates="aws_credential")

    # Ensure a user can only have one AWS credential entry
    __table_args__ = (UniqueConstraint('user_email', name='uq_user_aws_credential'),)

    def __repr__(self):
        return f"<AwsCredential(user_email='{self.user_email}', role_arn='{self.role_arn[:20]}...')>" 