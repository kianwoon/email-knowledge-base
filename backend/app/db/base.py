# backend/app/db/base.py

# Import Base from the class definition
from app.db.base_class import Base

# Import all SQLAlchemy models here so Base knows about them before create_all is called
from app.models.user import UserDB # Import your UserDB model
from app.models.token_models import TokenDB # Import your TokenDB model
# Add imports for any other SQLAlchemy models you create

# You can also re-export the engine from session if convenient for other parts of the app
from app.db.session import engine 