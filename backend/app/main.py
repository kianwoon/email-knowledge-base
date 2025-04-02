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

from app.config import settings
from app.routes import auth, email, review, vector, test

# Log environment variables for debugging
logger.debug(f"Starting application with environment variables:")
logger.debug(f"FRONTEND_URL: {settings.FRONTEND_URL}")
logger.debug(f"BACKEND_URL: {settings.BACKEND_URL}")
logger.debug(f"MS_REDIRECT_URI: {settings.MS_REDIRECT_URI}")
logger.debug(f"MS_CLIENT_ID: {settings.MS_CLIENT_ID[:5]}...{settings.MS_CLIENT_ID[-5:] if settings.MS_CLIENT_ID else 'Not set'}")
logger.debug(f"MS_TENANT_ID: {settings.MS_TENANT_ID[:5]}...{settings.MS_TENANT_ID[-5:] if settings.MS_TENANT_ID else 'Not set'}")

app = FastAPI()

# Configure CORS - must be added before any routes
origins = [
    "http://localhost:5173",  # Development frontend
    "http://localhost:5174",  # Alternative development port
    "http://localhost:5175",  # Alternative development port
    settings.FRONTEND_URL,    # Production frontend
]
logger.debug(f"Configuring CORS with allowed origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # Cache preflight requests for 24 hours
)

# Mount routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(email.router, prefix="/api/emails", tags=["emails"])
app.include_router(review.router, prefix="/api/review", tags=["Review Process"])
app.include_router(vector.router, prefix="/api/vector", tags=["Vector Database"])
app.include_router(test.router, prefix="/api/test", tags=["test"])

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
logger.debug(f"Mounting static directory: {static_dir}")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.debug("Health check endpoint called")
    return {
        "status": "online", 
        "message": "Email Knowledge Base API is running",
        "environment": {
            "FRONTEND_URL": settings.FRONTEND_URL,
            "MS_REDIRECT_URI": settings.MS_REDIRECT_URI,
            "static_dir": static_dir,
            "cwd": os.getcwd(),
            "listdir": os.listdir(".")
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.debug("Starting uvicorn server")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
