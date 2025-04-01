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

app = FastAPI(
    root_path="/api",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(email.router, prefix="/emails", tags=["emails"])
app.include_router(review.router, prefix="/review", tags=["Review Process"])
app.include_router(vector.router, prefix="/vector", tags=["Vector Database"])
app.include_router(test.router, prefix="/test", tags=["test"])

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
