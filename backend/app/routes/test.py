from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import os

router = APIRouter()

# Read the test page HTML content
test_page_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "test_auth_page.html")
with open(test_page_path, "r") as f:
    TEST_PAGE_HTML = f.read()

@router.get("/auth-test", response_class=HTMLResponse)
async def auth_test_page(request: Request):
    """Serve the Microsoft authentication test page"""
    return HTMLResponse(content=TEST_PAGE_HTML)
