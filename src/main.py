from fastapi import FastAPI

app = FastAPI(title="Token-Scoped Gateway")


@app.get("/health", tags=["System"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"} 