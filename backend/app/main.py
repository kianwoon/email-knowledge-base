from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from app.routes import auth, email, review, vector

app = FastAPI(
    title="Email Knowledge Base API",
    description="API for extracting knowledge from Outlook emails",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(email.router, prefix="/email", tags=["Email Management"])
app.include_router(review.router, prefix="/review", tags=["Review Process"])
app.include_router(vector.router, prefix="/vector", tags=["Vector Database"])

@app.get("/", tags=["Health Check"])
async def root():
    """Health check endpoint"""
    return {"status": "online", "message": "Email Knowledge Base API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
