import logging
import os
import sys
# Force UTC for JWT operations
# os.environ['TZ'] = 'UTC'
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter
# Import counters from the new metrics module
from app.metrics import COLUMN_BLOCKS, ATTACHMENT_REDACTIONS

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
from app.db.models.mcp_tool import MCPToolDB  # Add our MCPToolDB model
# Add other DB models used by the application here...
# from app.models.ingestion_job import IngestionJob # Example
# --- End Model Imports ---

from app.config import settings
# Remove the explicit module import we added before
# import app.models.processed_file 

# Import routers AFTER model imports
from app.routes import (
    auth, email, review, vector, knowledge, token,
    sharepoint, s3, azure_blob, custom_knowledge,
    tasks, export, user, schema, chat, shared_knowledge,
    jarvis_settings,
    # Add the new router import
    shared_knowledge_catalog,
    outlook_sync,
    mcp_tools,  # Add our mcp_tools router
    tool_execution,  # Add our new tool_execution router
    # Import the websockets router
    websockets
)
# Import the new shared_knowledge router
# from app.routes import shared_knowledge 
# Import the new chat router
# from app.routes import chat 
# Import the user router for API key management
# from app.routes import user
# Import the new schema router
# from app.routes import schema 
# Import services and dependencies needed for startup/app instance
from app.services import token_service 
from app.db.session import SessionLocal, engine
from app.db.job_mapping_db import initialize_db as initialize_job_mapping_db
# Import Base and engine from the new base module to ensure models are registered
from app.db.base import Base, engine 
from app.db.milvus_client import get_milvus_client, ensure_collection_exists
# Corrected import path for celery_app
from app.celery_app import celery_app

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

# Set specific loggers to WARNING to reduce verbosity
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING) # Also affects WebSocket connection open/closed msgs
logging.getLogger("app.routes.websockets").setLevel(logging.WARNING)
logging.getLogger("app.websocket").setLevel(logging.WARNING)

# Optionally set specific loggers to different levels if needed
# logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger.info(f"Root logger configured with level: {logging.getLevelName(log_level)}")
# --- End Logging Configuration ---

# --- Metrics Definition --- 
# -- Counters moved to app/metrics.py --
# COLUMN_BLOCKS = Counter(...)
# ATTACHMENT_REDACTIONS = Counter(...)

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
    lifespan=lifespan, # Use the new lifespan context manager
    # Disable automatic redirects from /path to /path/
    redirect_slashes=False
)

# Instrument the app after creation
# This automatically exposes /metrics and adds default metrics (latency, requests)
Instrumentator().instrument(app).expose(app)

# Register custom metrics so they are known to the instrumentator
Instrumentator().add(COLUMN_BLOCKS)
Instrumentator().add(ATTACHMENT_REDACTIONS)

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
        allow_credentials=True,  # Essential for cookies
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],  # Expose all headers to the frontend
    )
    logger.info(f"CORS enabled for origins: {settings.CORS_ALLOWED_ORIGINS} with credentials support")
else:
    logger.warning("CORS_ALLOWED_ORIGINS not set, CORS middleware not added.")

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])
app.include_router(email.router, prefix=f"{settings.API_PREFIX}/email", tags=["Email Interaction"])
app.include_router(review.router, prefix=f"{settings.API_PREFIX}/review", tags=["Review"])
app.include_router(vector.router, prefix=f"{settings.API_PREFIX}/vector", tags=["Vector Database"])
app.include_router(knowledge.router, prefix=f"{settings.API_PREFIX}/knowledge", tags=["Knowledge"])
app.include_router(token.router, prefix=f"{settings.API_PREFIX}/token", tags=["Token"])
app.include_router(sharepoint.router, prefix=f"{settings.API_PREFIX}/sharepoint", tags=["SharePoint"])
app.include_router(s3.router, prefix=f"{settings.API_PREFIX}/s3", tags=["S3"])
app.include_router(azure_blob.router, prefix=f"{settings.API_PREFIX}/azure_blob", tags=["Azure Blob Storage"])
app.include_router(custom_knowledge.router, prefix=f"{settings.API_PREFIX}/custom-knowledge", tags=["Custom Knowledge"])
app.include_router(tasks.router, prefix=f"{settings.API_PREFIX}/tasks", tags=["Tasks"])
app.include_router(export.router, prefix=f"{settings.API_PREFIX}/export", tags=["Export"])
app.include_router(chat.router, prefix=f"{settings.API_PREFIX}/chat", tags=["Chat"])
app.include_router(shared_knowledge.router, prefix=f"{settings.API_PREFIX}/shared-knowledge", tags=["Shared Knowledge"]) 
app.include_router(user.router, prefix=f"{settings.API_PREFIX}/user", tags=["User"])
app.include_router(schema.router, prefix=f"{settings.API_PREFIX}/schema", tags=["Schema"])
app.include_router(jarvis_settings.router, prefix=f"{settings.API_PREFIX}/jarvis-settings", tags=["Jarvis Settings"])
# Include the new router
app.include_router(shared_knowledge_catalog.router, prefix=f"{settings.API_PREFIX}/shared-knowledge-catalog", tags=["Shared Knowledge Catalog"])
app.include_router(outlook_sync.router, prefix=f"{settings.API_PREFIX}/email/sync", tags=["Outlook Sync"])
app.include_router(mcp_tools.router, prefix=f"{settings.API_PREFIX}/mcp", tags=["MCP Tools"])  # Include our mcp_tools router
app.include_router(tool_execution.router, prefix=f"{settings.API_PREFIX}/tool", tags=["Tool Execution"])

# Include the websockets router
app.include_router(websockets.router, prefix=f"{settings.API_PREFIX}/ws", tags=["WebSockets"])

# --- Log Registered Routes --- #
logger.info("--- Registered Routes --- DUMP START ---")
for route in app.routes:
    if hasattr(route, "path"):
        logger.info(f"Route: {route.path} Methods: {getattr(route, 'methods', 'N/A')}")
    elif hasattr(route, "routes"):
        # Handle mounted applications or APIRouters
        logger.info(f"Mounted Router/App: {route.path}")
        for sub_route in route.routes:
             if hasattr(sub_route, "path"):
                  logger.info(f"  - Sub-Route: {sub_route.path} Methods: {getattr(sub_route, 'methods', 'N/A')}")
logger.info("--- Registered Routes --- DUMP END ---")
# --- End Log ---

# Root endpoint (optional - for basic API check)
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"{app.title} is running!"}

# --- TEMPORARY DEBUG ENDPOINT --- #
@app.get("/debug-routes", tags=["Debug"])
async def list_routes():
    routes = []
    for route in app.routes:
        if hasattr(route, "path"):
            routes.append({"path": route.path, "methods": getattr(route, 'methods', None), "name": getattr(route, 'name', None)})
        elif hasattr(route, "routes"):
            # Handle sub-routers/mounted apps
            for sub_route in route.routes:
                if hasattr(sub_route, "path"):
                    # Combine parent path if available
                    parent_path = getattr(route, "path", "")
                    full_path = parent_path + sub_route.path
                    routes.append({"path": full_path, "methods": getattr(sub_route, 'methods', None), "name": getattr(sub_route, 'name', None)})
    return routes
# --- END TEMPORARY DEBUG ENDPOINT --- #

# Serve index.html for any other route (React Router handling)
templates = Jinja2Templates(directory="../../frontend/dist")

# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Convert the errors to a serializable format
    errors = []
    for error in exc.errors():
        # Ensure the error context is serializable
        if 'ctx' in error and 'error' in error['ctx'] and isinstance(error['ctx']['error'], Exception):
            # Convert the exception to a string
            error['ctx']['error'] = str(error['ctx']['error'])
        errors.append(error)
    
    logger.error(f"Validation error for request {request.method} {request.url}: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )

# Mount static files (Optional - if serving frontend from backend)
# Ensure the path exists and is correct in your environment (e.g., Docker container)
# frontend_build_dir = "/app/static"
# if os.path.isdir(frontend_build_dir):
#     logger.info(f"Mounting static files from {frontend_build_dir}")
#     app.mount("/", StaticFiles(directory=frontend_build_dir, html=True), name="static")
# else:
#     logger.info(f"Static files directory not found: {frontend_build_dir}, skipping static file mount.")

# Celery task route (example - adjust as needed)
@app.post("/api/v1/trigger-task", status_code=202)
async def trigger_task():
    # Implementation of the task trigger logic
    pass

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting uvicorn development server on {settings.DEV_SERVER_HOST}:{settings.DEV_SERVER_PORT} with reload={'enabled' if settings.DEV_SERVER_RELOAD else 'disabled'}")
    uvicorn.run(
        "app.main:app", 
        host=settings.DEV_SERVER_HOST, 
        port=settings.DEV_SERVER_PORT, 
        reload=settings.DEV_SERVER_RELOAD
    )
