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

from app.routes import auth, email, review, vector, webhooks, websockets

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

app = FastAPI(title="Email Knowledge Base API")

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

# Mount routes - Ensure all use /api prefix internally
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["auth"])
app.include_router(email.router, prefix=f"{settings.API_PREFIX}/emails", tags=["emails"])
app.include_router(review.router, prefix=f"{settings.API_PREFIX}/review", tags=["Review Process"])
app.include_router(vector.router, prefix=f"{settings.API_PREFIX}/vector", tags=["Vector Database"])
# Assuming WEBHOOK_PREFIX is set to /api in production environment for consistency
app.include_router(webhooks.router, prefix=settings.WEBHOOK_PREFIX, tags=["webhooks"])
app.include_router(websockets.router, prefix=f"{settings.API_PREFIX}", tags=["websockets"])

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
logger.debug(f"Mounting static directory: {static_dir}")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Email Knowledge Base API"}

@app.get(f"{settings.API_PREFIX}/health") # Add /api prefix back
async def health_check():
    """Health check endpoint"""
    logger.debug("Health check endpoint called")
    return {
        "status": "online", 
        "message": "Email Knowledge Base API is running",
        "environment": {
            "FRONTEND_URL": settings.FRONTEND_URL,
            "MS_REDIRECT_URI": settings.MS_REDIRECT_URI,
            "API_PREFIX": settings.API_PREFIX, # Add API_PREFIX back for info
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
