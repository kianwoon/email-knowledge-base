import typing
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from app.db.base_class import Base

if typing.TYPE_CHECKING:
    from .user import UserDB  # Import for type hinting only

class AwsCredential(Base):
    __tablename__ = "aws_credentials"  # Using the specified table name

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    # Link to users table via email (the primary key of UserDB)
    user_email: Mapped[str] = Column(String, ForeignKey("users.email"), unique=True, nullable=False, index=True)
    role_arn: Mapped[str] = Column(String, nullable=False)

    # Define the relationship using string literals for runtime
    # Type hint uses the TYPE_CHECKING import
    user: Mapped["UserDB"] = relationship("UserDB", back_populates="aws_credential") 