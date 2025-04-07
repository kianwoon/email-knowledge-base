from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
import os
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("app")

try:
    from app.config import settings
except ValueError as e:
    logger.error(f"CRITICAL ERROR loading configuration: {e}")
    logger.error("Please ensure all required environment variables are set in your .env file or system environment.")
    sys.exit(1) # Exit if configuration fails

# Import DB functions for startup event
from app.db.qdrant_client import get_qdrant_client, ensure_collection_exists
from app.routes import auth, email, review, vector, webhooks, websockets, knowledge

# Log critical environment variables for debugging
logger.debug("--- Application Startup --- ")
logger.debug(f"ENVIRONMENT: {settings.ENVIRONMENT}")
logger.debug(f"DEBUG: {settings.DEBUG}")
logger.debug(f"FRONTEND_URL: {settings.FRONTEND_URL}")
logger.debug(f"BACKEND_URL: {settings.BACKEND_URL}")
logger.debug(f"CORS Allowed Origins: {settings.CORS_ALLOWED_ORIGINS}")
logger.debug(f"Webhook Prefix: {settings.WEBHOOK_PREFIX}")
# Only log sensitive info like this in DEBUG mode or be very careful
if settings.DEBUG:
    logger.debug(f"MS_REDIRECT_URI: {settings.MS_REDIRECT_URI}")
    logger.debug(f"MS_CLIENT_ID: {settings.MS_CLIENT_ID[:5]}...{settings.MS_CLIENT_ID[-5:] if settings.MS_CLIENT_ID else 'Not set'}")
    logger.debug(f"MS_TENANT_ID: {settings.MS_TENANT_ID[:5]}...{settings.MS_TENANT_ID[-5:] if settings.MS_TENANT_ID else 'Not set'}")

app = FastAPI(
    title="Knowledge Base Builder API",
    description="API for managing emails, analysis, and knowledge base vectors.",
    version="0.1.0"
)

# Add the state dictionary here
app.state.job_mapping_store = {}

# --- Add Startup Event --- 
@app.on_event("startup")
async def startup_db_check():
    logger.info("Running startup event: Ensuring Qdrant collection exists...")
    try:
        qdrant_client = get_qdrant_client() # Get client instance
        ensure_collection_exists(qdrant_client) # Run the check/creation logic
        logger.info("Startup event: Qdrant collection check complete.")
    except Exception as e:
        logger.error(f"Startup event FAILED: Could not ensure Qdrant collection. Error: {e}", exc_info=True)
        # Depending on policy, you might want to exit if DB connection fails on startup
        # sys.exit(1)
# --- End Startup Event ---

# Configure CORS using settings
logger.info(f"Configuring CORS with allowed origins from settings: {settings.CORS_ALLOWED_ORIGINS}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS, # Use the list from settings
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # Cache preflight requests for 24 hours
)

# --- Mount Routes (WITH /api prefix for consistency) ---
# This assumes Koyeb is configured to forward /api paths without stripping
api_prefix = "/api"
logger.info(f"Including API routers with prefix: {api_prefix}")
app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["Auth"])
app.include_router(email.router, prefix=f"{api_prefix}/emails", tags=["Emails"])
app.include_router(review.router, prefix=f"{api_prefix}/review", tags=["Review Process"])
app.include_router(vector.router, prefix=f"{api_prefix}/vector", tags=["Vector Database"])
app.include_router(knowledge.router, prefix=f"{api_prefix}/knowledge", tags=["Knowledge"])

# REMOVED Routes WITHOUT /api prefix 
# logger.info("Including API routers WITHOUT prefix (for Koyeb compatibility)...")
# app.include_router(auth.router, prefix="/auth", tags=["Auth"])
# ... removed other non-api routes

# Webhook/WebSocket prefixes remain unchanged
logger.info(f"Including Webhook router with prefix: {settings.WEBHOOK_PREFIX}")
app.include_router(webhooks.router, prefix=settings.WEBHOOK_PREFIX, tags=["Webhooks"])
logger.info("Including WebSocket router with prefix: ''")
app.include_router(websockets.router, prefix="", tags=["Websockets"])

# Mount static files directory (remains unchanged)
static_dir = os.path.join(os.path.dirname(__file__), "static")
logger.debug(f"Mounting static directory: {static_dir}")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return {"message": "Welcome to the Knowledge Base Builder API"}

@app.get("/health") # No /api prefix internally
async def health_check():
    """Health check endpoint"""
    logger.debug("Health check endpoint called")
    return {
        "status": "online", 
        "message": "Email Knowledge Base API is running",
        "environment": {
            "FRONTEND_URL": settings.FRONTEND_URL,
            "MS_REDIRECT_URI": settings.MS_REDIRECT_URI,
            "IS_PRODUCTION": settings.IS_PRODUCTION,
            "static_dir": static_dir,
            "cwd": os.getcwd(),
            "listdir": os.listdir(".")
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting uvicorn development server on {settings.DEV_SERVER_HOST}:{settings.DEV_SERVER_PORT} with reload={'enabled' if settings.DEV_SERVER_RELOAD else 'disabled'}")
    uvicorn.run(
        "app.main:app", 
        host=settings.DEV_SERVER_HOST, 
        port=settings.DEV_SERVER_PORT, 
        reload=settings.DEV_SERVER_RELOAD
    )
