import logging
import sys
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.config import settings
# Import routers
from app.routes import auth, email, review, vector, webhooks, websockets, knowledge, token 
# Import services and dependencies needed for startup/app instance
from app.services import token_service 
from app.db.qdrant_client import get_qdrant_client
# Import Base and engine from the new base module to ensure models are registered
from app.db.base import Base, engine 

# Configure logging
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Log critical environment variables for debugging
logger.info(f"Running with environment: {settings.ENVIRONMENT}")
logger.debug(f"Allowed origins: {settings.CORS_ALLOWED_ORIGINS}")

# API Prefix
api_prefix = "/api/v1"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    logger.info("Application starting up...")
    
    # --- Initialize Shared State --- 
    app.state.job_mapping_store = {} # Initialize the job mapping store
    logger.info("Initialized shared job_mapping_store on app state.")
    # --- End Shared State Init ---

    # Ensure token collection exists on startup
    try:
        # Use the correctly imported function
        qdrant_client = get_qdrant_client()
        token_service.ensure_token_collection(qdrant_client)
        logger.info("Checked/Ensured token collection exists.")
    except Exception as e:
        logger.error(f"Failed to ensure token collection on startup: {e}", exc_info=True)
        # Decide if this should prevent startup? For now, just log.
        
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
    app.state.job_mapping_store = None 

app = FastAPI(
    title="Knowledge Base Builder API", 
    version="1.0.0",
    lifespan=lifespan # Use the new lifespan context manager
)

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
app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["Authentication"])
app.include_router(email.router, prefix=f"{api_prefix}/email", tags=["Email Interaction"])
app.include_router(review.router, prefix=f"{api_prefix}/review", tags=["Review"])
app.include_router(vector.router, prefix=f"{api_prefix}/vector", tags=["Vector Database"])
app.include_router(knowledge.router, prefix=f"{api_prefix}/knowledge", tags=["Knowledge"])
app.include_router(token.router, prefix=f"{api_prefix}/token", tags=["Token"])
app.include_router(webhooks.router, prefix=f"{api_prefix}/webhooks", tags=["Webhooks"])
app.include_router(websockets.router, prefix=f"{api_prefix}/ws", tags=["Websockets"])

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
