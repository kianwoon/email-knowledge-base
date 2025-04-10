"""Base model configuration for SQLAlchemy models."""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any, TypeVar, Generic

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass 