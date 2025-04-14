import uuid
from datetime import datetime
from enum import Enum # Import standard Python Enum
from sqlalchemy import (Column, String, Integer, Boolean, DateTime, ForeignKey,
                      Text, Enum as SQLAlchemyEnum)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base
from .user import UserDB # Correctly import the DB model
import enum

# Define Enum for Authentication Types
class AzureAuthType(str, enum.Enum):
    CONNECTION_STRING = "connection_string"
    ACCOUNT_KEY = "account_key"
    # Future types
    # SAS_TOKEN = "sas_token"
    # SERVICE_PRINCIPAL = "service_principal"
    # MANAGED_IDENTITY = "managed_identity"

class AzureBlobConnection(Base):
    __tablename__ = "azure_blob_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    account_name = Column(String, nullable=True)
    # Pass the correct Enum class to SQLAlchemyEnum
    auth_type = Column(SQLAlchemyEnum(AzureAuthType, name="azureauthtype", inherit_schema=True),
                       nullable=False,
                       default=AzureAuthType.CONNECTION_STRING)
    # Make credentials non-nullable again
    credentials = Column(Text, nullable=False)
    container_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("UserDB", back_populates="azure_blob_connections")

    # If sync jobs table is added:
    # sync_jobs = relationship("AzureBlobSyncJob", back_populates="connection", cascade="all, delete-orphan") 