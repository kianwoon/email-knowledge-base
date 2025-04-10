"""Module for defining SQLAlchemy relationships between models."""

def setup_relationships():
    """Set up relationships between models after they are defined."""
    from .user import UserDB
    from .api_key import APIKeyDB

    # Set up User-APIKey relationship
    UserDB.api_keys = relationship(
        "APIKeyDB",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    APIKeyDB.user = relationship(
        "UserDB",
        back_populates="api_keys"
    ) 