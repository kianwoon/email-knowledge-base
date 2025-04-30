import logging
import os
import sys
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

# +++ Explicitly import ALL necessary SQLAlchemy Models +++
# This ensures they are registered with Base.metadata before routes are loaded
from app.models.user import UserDB
from app.models.api_key import APIKeyDB
from app.models.user_preference import UserPreferenceDB
from app.db.models.processed_file import ProcessedFile 
from app.models.custom_knowledge_file import CustomKnowledgeFile # Keep if used
from app.models.aws_credential import AwsCredential
from app.models.azure_blob import AzureBlobConnection
from app.models.azure_blob_sync_item import AzureBlobSyncItem
from app.models.sharepoint_sync import SharePointSyncItem
# Add other DB models used by the application here...
# from app.models.ingestion_job import IngestionJob # Example
# --- End Model Imports ---

from app.config import settings
# Remove the explicit module import we added before
# import app.models.processed_file 

# Import routers AFTER model imports
from app.routes import auth, email, review, vector, webhooks, websockets, knowledge, token, tasks 
# Import the new shared_knowledge router
from app.routes import shared_knowledge 
# Import the new chat router
from app.routes import chat 
# Import the user router for API key management
from app.routes import user
# Import the new SharePoint router
from app.routes import sharepoint 
# Import the new S3 router
from app.routes import s3 as s3_router
# Import the new Azure Blob router
from app.routes import azure_blob
# Import the new custom_knowledge router
from app.routes import custom_knowledge
# Import services and dependencies needed for startup/app instance
from app.services import token_service 
from app.db.session import SessionLocal, engine
from app.db.job_mapping_db import initialize_db as initialize_job_mapping_db
# Import Base and engine from the new base module to ensure models are registered
from app.db.base import Base, engine 
from app.db.milvus_client import get_milvus_client, ensure_collection_exists
from app.db.init_db import init_db # Import the init_db function

# Configure logging
logger = logging.getLogger("app")

# Log critical environment variables for debugging
logger.info(f"Running with environment: {settings.ENVIRONMENT}")
logger.debug(f"Allowed origins: {settings.CORS_ALLOWED_ORIGINS}")

# API Prefix
api_prefix = settings.API_PREFIX

# --- Logging Configuration ---
# Determine log level based on settings
log_level = logging.DEBUG if settings.DEBUG else logging.INFO
# FORCE DEBUG FOR NOW
# log_level = logging.DEBUG

# Configure root logger
logging.basicConfig(level=log_level, stream=sys.stdout, 
                    format='%(levelname)s:%(name)s:%(lineno)d - %(message)s') # Slightly adjusted format for more detail

# Optionally set specific loggers to different levels if needed
# logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger.info(f"Root logger configured with level: {logging.getLevelName(log_level)}")
# --- End Logging Configuration ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up...")
    
    # --- Initialize the shared dictionary on app state --- 
    # app.state.job_mapping_store = {}
    # logger.info("Initialized shared job_mapping_store on app state.")
    # --- This is no longer needed as we use Qdrant for mapping ---
    
    # Initialize SQLite Job Mapping DB
    initialize_job_mapping_db()
    
    # Ensure Qdrant collection for tokens exists
    try:
        # Use the correctly imported function
        # client = get_qdrant_client()
        # ensure_token_collection_exists(client) # <-- This function call needs to be handled elsewhere, likely token_service
        # logger.info("Checked/Ensured token collection exists.")
        # Let's rely on the token_service to handle this check as needed.
        logger.info("Token collection check will be handled by token_service.")
    except Exception as e:
        logger.error(f"Error during token collection check on startup: {e}", exc_info=True)

    # --- Database Initialization --- 
    logger.info("Creating database tables based on models...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        # Depending on the desired behavior, you might want to raise the exception
        # or allow the app to continue without the tables (which will likely cause errors later).
        # raise e 
    # --- End Database Initialization ---
    
    logger.info("Application startup complete.")
    yield
    # Code to run on shutdown
    logger.info("Application shutting down...")
    # Optionally clear state if needed
    # app.state.job_mapping_store = None 

app = FastAPI(
    title="Knowledge Base Builder API", 
    description="API for managing email processing, knowledge base, and analysis.",
    version="0.1.0",
    lifespan=lifespan # Use the new lifespan context manager
)

# Middleware for logging requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log request details safely
    client_host = request.client.host if request.client else "unknown_client"
    logger.info(f"Request: {request.method} {request.url.path} {client_host}")
    response = await call_next(request)
    # Log response status code
    logger.info(f"Response: {response.status_code}")
    return response

# CORS Middleware
if settings.CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS, 
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS enabled for origins: {settings.CORS_ALLOWED_ORIGINS}")
else:
    logger.warning("CORS_ALLOWED_ORIGINS not set, CORS middleware not added.")

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])
app.include_router(email.router, prefix=f"{settings.API_PREFIX}/email", tags=["Email Interaction"])
app.include_router(review.router, prefix=f"{settings.API_PREFIX}/review", tags=["Review"])
app.include_router(vector.router, prefix=f"{settings.API_PREFIX}/vector", tags=["Vector Database"])
app.include_router(knowledge.router, prefix=f"{settings.API_PREFIX}/knowledge", tags=["Knowledge"])
app.include_router(token.router, prefix=f"{settings.API_PREFIX}/token", tags=["Token"])
app.include_router(webhooks.router, prefix=f"{settings.API_PREFIX}/webhooks", tags=["Webhooks"])
app.include_router(websockets.router, prefix=f"{settings.API_PREFIX}/ws", tags=["Websockets"])
app.include_router(shared_knowledge.router, prefix=settings.API_PREFIX, tags=["Shared Knowledge"])
app.include_router(tasks.router, prefix=f"{settings.API_PREFIX}/tasks", tags=["Tasks"])

# --- Include Chat Router --- 
app.include_router(chat.router, prefix=f"{settings.API_PREFIX}/chat", tags=["Chat"])
# --- End Include ---

# --- Include User Router ---
app.include_router(user.router, prefix=f"{settings.API_PREFIX}/user", tags=["User"])
# --- End Include ---

# --- Include SharePoint Router ---
app.include_router(
    sharepoint.router, 
    prefix=f"{settings.API_PREFIX}/sharepoint", 
    tags=["SharePoint"]
)
# --- End Include ---

# --- Include S3 Router ---
app.include_router(
    s3_router.router, 
    prefix=f"{settings.API_PREFIX}/s3", # Set the prefix for S3 routes
    tags=["S3"] # Tag for API docs
)
# --- End Include ---

# --- Include Azure Blob Router ---
app.include_router(
    azure_blob.router,
    prefix=f"{settings.API_PREFIX}/azure_blob",
    tags=["Azure Blob Storage"]
)
# --- End Include ---

# --- Include Custom Knowledge Router ---
app.include_router(custom_knowledge.router, prefix=f"{settings.API_PREFIX}/custom-knowledge", tags=["Custom Knowledge"])
# --- End Include ---

# Root endpoint (optional - for basic API check)
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"{app.title} is running!"}

# Serve index.html for any other route (React Router handling)
templates = Jinja2Templates(directory="../../frontend/dist")

# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error for request {request.method} {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )

# Mount static files (Optional - if serving frontend from backend)
# Ensure the path exists and is correct in your environment (e.g., Docker container)
# frontend_build_dir = "/app/static"
# if os.path.isdir(frontend_build_dir):
#     logger.info(f"Mounting static files from {frontend_build_dir}")
#     app.mount("/", StaticFiles(directory=frontend_build_dir, html=True), name="static")
# else:
#     logger.info(f"Static files directory not found: {frontend_build_dir}, skipping static file mount.")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting uvicorn development server on {settings.DEV_SERVER_HOST}:{settings.DEV_SERVER_PORT} with reload={'enabled' if settings.DEV_SERVER_RELOAD else 'disabled'}")
    uvicorn.run(
        "app.main:app", 
        host=settings.DEV_SERVER_HOST, 
        port=settings.DEV_SERVER_PORT, 
        reload=settings.DEV_SERVER_RELOAD
    )
