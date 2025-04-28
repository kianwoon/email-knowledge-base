# backend/app/db/base.py
# Remove logging import if no longer needed
# import logging
# Import Base from the class definition
from app.db.base_class import Base

# --- REMOVE ALL MODEL IMPORTS FROM HERE --- 
# logger = logging.getLogger(__name__)
# logger.info("Importing models into Base registry...")
# try:
#     from app.models.user import UserDB
#     # ... (removed other model imports) ...
#     logger.info("Successfully imported core models into Base registry.")
# except ImportError as e:
#     logger.error(f"Error importing models in base.py: {e}", exc_info=True)
#     # raise e

# Re-export the engine from session 
from app.db.session import engine

# Optional: Re-export Base itself if other modules import it from here
# __all__ = ["Base", "engine"] # Only if needed