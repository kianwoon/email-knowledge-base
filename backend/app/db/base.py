# backend/app/db/base.py

# Import Base from the class definition
from app.db.base_class import Base

# Import all SQLAlchemy models here so Base knows about them before create_all is called
from app.models.user import UserDB # Import your UserDB model
from app.models.token_models import TokenDB # Import your TokenDB model
from app.models.api_key import APIKeyDB # Import your APIKeyDB model
from app.models.user_preference import UserPreferenceDB # Import your UserPreferenceDB model
from app.db.models.sharepoint_sync_item import SharePointSyncItem # <<< ADDED
# Add imports for any other SQLAlchemy models you create

# You can also re-export the engine from session if convenient for other parts of the app
from app.db.session import engine 