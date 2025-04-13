from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class AwsCredential(Base):
    """SQLAlchemy model for storing AWS credentials (Role ARN) per user."""
    __tablename__ = 'aws_credentials'

    id = Column(Integer, primary_key=True, index=True)
    # Assuming user_email is the identifier linking to your User model
    # If you have a User table with an ID, you might use ForeignKey('users.id')
    user_email = Column(String, unique=True, index=True, nullable=False) 
    role_arn = Column(String, nullable=False)

    # Optional: Define a relationship if you have a User model
    # user = relationship("UserDB", back_populates="aws_credential") 

    # Ensure a user can only have one AWS credential entry
    __table_args__ = (UniqueConstraint('user_email', name='uq_user_aws_credential'),)

    def __repr__(self):
        return f"<AwsCredential(user_email='{self.user_email}', role_arn='{self.role_arn[:20]}...')>" 