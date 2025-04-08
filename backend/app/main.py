import logging
import sys
from fastapi import FastAPI, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.config import settings
# Import routers
from app.routes import auth, email, review, vector, webhooks, websockets, knowledge, token 
# Import the new shared_knowledge router
from app.routes import shared_knowledge 
# Import services and dependencies needed for startup/app instance
from app.services import token_service 
from app.db.qdrant_client import get_qdrant_client
from app.db.session import SessionLocal
from app.db.job_mapping_db import initialize_db as initialize_job_mapping_db
# Import Base and engine from the new base module to ensure models are registered
from app.db.base import Base, engine 

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Log critical environment variables for debugging
logger.info(f"Running with environment: {settings.ENVIRONMENT}")
logger.debug(f"Allowed origins: {settings.CORS_ALLOWED_ORIGINS}")

# API Prefix
api_prefix = settings.API_PREFIX

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
    version="1.0.0",
    lifespan=lifespan # Use the new lifespan context manager
)

# --- Add Middleware for Path Logging HERE --- 
@app.middleware("http")
async def log_request_path(request: Request, call_next):
    logger.info(f"MIDDLEWARE: Received request for path: {request.url.path}")
    response = await call_next(request)
    return response
# --- End Middleware ---

# CORS Middleware
if settings.CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip() for origin in settings.CORS_ALLOWED_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.warning("CORS is not configured. Allowing all origins.")
    # Allow all origins if not specified (use with caution)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Authentication"])
app.include_router(email.router, prefix=f"{settings.API_PREFIX}/email", tags=["Email Interaction"])
app.include_router(review.router, prefix=f"{settings.API_PREFIX}/review", tags=["Review"])
app.include_router(vector.router, prefix=f"{settings.API_PREFIX}/vector", tags=["Vector Database"])
app.include_router(knowledge.router, prefix=f"{settings.API_PREFIX}/knowledge", tags=["Knowledge"])
app.include_router(token.router, prefix=f"{settings.API_PREFIX}/token", tags=["Token"])
app.include_router(webhooks.router, prefix=f"{settings.API_PREFIX}/webhooks", tags=["Webhooks"])
app.include_router(websockets.router, prefix=f"{settings.API_PREFIX}/ws", tags=["Websockets"])
# Add the new router
app.include_router(shared_knowledge.router, prefix=settings.API_PREFIX, tags=["Shared Knowledge"]) # Prefix includes /api/v1

# Root endpoint (optional - for basic API check)
@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"{app.title} is running!"}

# Serve index.html for any other route (React Router handling)
templates = Jinja2Templates(directory="../../frontend/dist")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting uvicorn development server on {settings.DEV_SERVER_HOST}:{settings.DEV_SERVER_PORT} with reload={'enabled' if settings.DEV_SERVER_RELOAD else 'disabled'}")
    uvicorn.run(
        "app.main:app", 
        host=settings.DEV_SERVER_HOST, 
        port=settings.DEV_SERVER_PORT, 
        reload=settings.DEV_SERVER_RELOAD
    )
