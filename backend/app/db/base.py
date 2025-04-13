# backend/app/db/base.py

# Import Base from the class definition
from app.db.base_class import Base

# --- REMOVE ALL MODEL IMPORTS FROM HERE --- 
# # Import all SQLAlchemy models here so Base knows about them before create_all is called
# from app.models.user import UserDB 
# from app.models.token_models import TokenDB 
# from app.models.api_key import APIKeyDB 
# from app.models.user_preference import UserPreferenceDB 
# from app.db.models.sharepoint_sync_item import SharePointSyncItem 
# from app.db.models.s3_sync_item import S3SyncItem 
# from app.db.models.aws_credential import AwsCredential 

# Re-export the engine from session 
from app.db.session import engine 