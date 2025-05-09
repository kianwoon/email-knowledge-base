from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

class MCPToolDB(Base):
    """SQLAlchemy model for MCP tools."""
    __tablename__ = "mcp_tools"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    entrypoint: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, default="1.0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_email: Mapped[str] = mapped_column(ForeignKey("users.email"), index=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship to user
    user = relationship("UserDB", back_populates="mcp_tools")
    
    def __repr__(self) -> str:
        return f"<MCPToolDB(id={self.id}, name='{self.name}', description='{self.description}', user_email='{self.user_email}')>" 