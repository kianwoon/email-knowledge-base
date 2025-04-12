"""Base model and common imports."""
# from sqlalchemy.ext.declarative import declarative_base # Removed
from sqlalchemy.orm import registry

mapper_registry = registry()
# Base = declarative_base() # <<< REMOVE THIS LINE 