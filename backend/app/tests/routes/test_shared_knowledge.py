import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, Generator
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

# Assuming your main app is in backend/app/main.py
# Adjust the import path if necessary
from app.main import app 
from app.db.session import get_db # For overriding dependency
from app.models.token_models import TokenDB, TokenType # Import TokenDB and TokenType
from app.crud import token_crud # To create tokens
from app.dependencies.auth import get_current_active_user # If needed for mocking
from app.models.user import User # If needed for mocking
from app.routes.shared_knowledge import get_validated_token # Assuming get_validated_token is directly in shared_knowledge or imported there
# We need to mock functions in the module where they are *used*
SEARCH_SERVICE_PATH = "app.routes.shared_knowledge" 

# TODO: Configure a test database session fixture if needed
# Example (requires test DB setup):
# from app.db.session import TestingSessionLocal
# @pytest.fixture(scope="function")
# def db() -> Generator:
#     db = TestingSessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# Test client fixture
@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    # Clear overrides at start just in case
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides = {}
    yield TestClient(app)
    # Restore original overrides after tests
    app.dependency_overrides = original_overrides

# Mock user for dependency injection if routes require authentication beyond the token
@pytest.fixture
def mock_user() -> User:
    return User(email="test@example.com", display_name="Test User", id="test-user-id")

# Mock database session fixture (in-memory or alternative for isolated tests)
@pytest.fixture
def mock_db_session(mocker) -> Session:
    # This is a simple mock. For actual DB interaction tests, 
    # you'd need a real test DB session or a more sophisticated mock.
    mock_session = MagicMock(spec=Session)
    # Mock common methods if needed, e.g., mock_session.query.return_value...
    return mock_session

# Override database dependency for tests using the mock session
# app.dependency_overrides[get_db] = lambda: mock_db_session # Needs pytest-mock

# --- Mock Data --- 

MOCK_SEARCH_RESULTS = [
    {
        'id': 'doc1',
        'score': 0.9,
        'metadata': {
            'col_a': 'value_a1',
            'col_b': 'value_b1',
            'col_c': 'value_c1',
            'attachments': [{'name': 'file1.pdf'}]
        },
         'content': 'content1' # Add content field as expected by logic
    },
    {
        'id': 'doc2',
        'score': 0.8,
        'metadata': {
            'col_a': 'value_a2',
            'col_b': 'value_b2',
            'col_c': 'value_c2'
             # No attachments key
        },
        'content': 'content2' # Add content field
    }
]

# --- Helper to create mock tokens --- 
def create_mock_token(
    token_id: int = 1,
    owner_email: str = "test@example.com",
    allow_columns: Optional[List[str]] = None,
    allow_attachments: bool = True,
    row_limit: int = 100,
    can_export_vectors: bool = False,
    **kwargs
) -> TokenDB:
    # Create a mock TokenDB object - no DB interaction needed for these tests
    # if we mock the dependency that fetches the token
    mock_token = MagicMock(spec=TokenDB)
    mock_token.id = token_id
    mock_token.owner_email = owner_email
    mock_token.allow_columns = allow_columns
    mock_token.allow_attachments = allow_attachments
    mock_token.row_limit = row_limit
    mock_token.can_export_vectors = can_export_vectors
    mock_token.hashed_token = "mock_hash" # Needed for export model potentially
    mock_token.token_type = TokenType.PUBLIC # Default type
    mock_token.sensitivity = "internal" # Default sensitivity
    mock_token.is_active = True
    mock_token.expiry = None
    mock_token.allow_rules = []
    mock_token.deny_rules = []
    # Add other fields as needed by TokenExport or other logic
    for key, value in kwargs.items():
        setattr(mock_token, key, value)
    return mock_token

# --- Test Functions --- 

# Placeholder for the actual tests
def test_search_placeholder():
    assert True

@pytest.mark.asyncio
async def test_search_column_projection_applied(client: TestClient):
    """Test that allow_columns correctly projects metadata."""
    test_token = create_mock_token(allow_columns=['col_a', 'col_c'], allow_attachments=True)
    # Mock context managers need correct indentation
    with patch(f'{SEARCH_SERVICE_PATH}.search_milvus_knowledge', new_callable=AsyncMock) as mock_search,
         patch(f'{SEARCH_SERVICE_PATH}.rerank_results', new_callable=AsyncMock) as mock_rerank,
         patch(f'{SEARCH_SERVICE_PATH}.token_crud.create_milvus_filter_from_token') as mock_filter,
         patch(f'{SEARCH_SERVICE_PATH}.create_embedding', new_callable=AsyncMock) as mock_embed:
        
        mock_search.return_value = [MOCK_SEARCH_RESULTS]
        mock_rerank.return_value = MOCK_SEARCH_RESULTS
        mock_filter.return_value = "mock_filter_expression"
        mock_embed.return_value = [0.1] * 100

        # Temporarily override dependency for this specific test
        original_override = app.dependency_overrides.get(get_validated_token)
        app.dependency_overrides[get_validated_token] = lambda: test_token
        try:
            headers = {"Authorization": f"Bearer faketokenvalue"}
            response = client.get("/shared-knowledge/search?query=test", headers=headers)

            assert response.status_code == 200
            results = response.json()
            assert len(results) == 2
            assert 'metadata' in results[0]
            assert list(results[0]['metadata'].keys()) == ['col_a', 'col_c'] 
            assert results[0]['metadata']['col_a'] == 'value_a1'
            assert results[0]['metadata']['col_c'] == 'value_c1'
            assert 'col_b' not in results[0]['metadata']
            # Attachment key ('attachments') was NOT in allow_columns, so it should be filtered out
            assert 'attachments' not in results[0]['metadata'] 
            assert 'metadata' in results[1]
            assert list(results[1]['metadata'].keys()) == ['col_a', 'col_c']
            assert results[1]['metadata']['col_a'] == 'value_a2'
            assert results[1]['metadata']['col_c'] == 'value_c2'
            assert 'col_b' not in results[1]['metadata']
            assert 'id' in results[0]
            assert 'score' in results[0]
        finally:
             # Restore or remove the override
             if original_override is not None:
                 app.dependency_overrides[get_validated_token] = original_override
             elif get_validated_token in app.dependency_overrides:
                 del app.dependency_overrides[get_validated_token]

@pytest.mark.asyncio
async def test_search_column_projection_none(client: TestClient):
    """Test that if allow_columns is None, all metadata is returned (respecting attachment flag)."""
    test_token = create_mock_token(allow_columns=None, allow_attachments=True)
    with patch(f'{SEARCH_SERVICE_PATH}.search_milvus_knowledge', new_callable=AsyncMock) as mock_search,
         patch(f'{SEARCH_SERVICE_PATH}.rerank_results', new_callable=AsyncMock) as mock_rerank,
         patch(f'{SEARCH_SERVICE_PATH}.token_crud.create_milvus_filter_from_token') as mock_filter,
         patch(f'{SEARCH_SERVICE_PATH}.create_embedding', new_callable=AsyncMock) as mock_embed:
        
        mock_search.return_value = [MOCK_SEARCH_RESULTS]
        mock_rerank.return_value = MOCK_SEARCH_RESULTS
        mock_filter.return_value = "mock_filter_expression"
        mock_embed.return_value = [0.1] * 100

        original_override = app.dependency_overrides.get(get_validated_token)
        app.dependency_overrides[get_validated_token] = lambda: test_token
        try:
            headers = {"Authorization": f"Bearer faketokenvalue"}
            response = client.get("/shared-knowledge/search?query=test", headers=headers)
            assert response.status_code == 200
            results = response.json()
            assert len(results) == 2
            assert 'metadata' in results[0]
            # Should include attachments because allow_attachments=True and allow_columns=None
            assert set(results[0]['metadata'].keys()) == {'col_a', 'col_b', 'col_c', 'attachments'}
            assert results[0]['metadata']['attachments'] == MOCK_SEARCH_RESULTS[0]['metadata']['attachments']
            assert 'metadata' in results[1]
            assert set(results[1]['metadata'].keys()) == {'col_a', 'col_b', 'col_c'}
        finally:
            # Restore or remove the override
            if original_override is not None:
                app.dependency_overrides[get_validated_token] = original_override
            elif get_validated_token in app.dependency_overrides:
                del app.dependency_overrides[get_validated_token]

@pytest.mark.asyncio
async def test_search_attachment_filtering_disallowed(client: TestClient):
    """Test that attachments are removed if allow_attachments is False."""
    test_token = create_mock_token(allow_attachments=False, allow_columns=None)
    with patch(f'{SEARCH_SERVICE_PATH}.search_milvus_knowledge', new_callable=AsyncMock) as mock_search,
         patch(f'{SEARCH_SERVICE_PATH}.rerank_results', new_callable=AsyncMock) as mock_rerank,
         patch(f'{SEARCH_SERVICE_PATH}.token_crud.create_milvus_filter_from_token') as mock_filter,
         patch(f'{SEARCH_SERVICE_PATH}.create_embedding', new_callable=AsyncMock) as mock_embed:
        
        mock_search.return_value = [MOCK_SEARCH_RESULTS]
        mock_rerank.return_value = MOCK_SEARCH_RESULTS
        mock_filter.return_value = "mock_filter_expression"
        mock_embed.return_value = [0.1] * 100

        original_override = app.dependency_overrides.get(get_validated_token)
        app.dependency_overrides[get_validated_token] = lambda: test_token
        try:
            headers = {"Authorization": f"Bearer faketokenvalue"}
            response = client.get("/shared-knowledge/search?query=test", headers=headers)
            assert response.status_code == 200
            results = response.json()
            assert len(results) == 2
            assert 'metadata' in results[0]
            assert set(results[0]['metadata'].keys()) == {'col_a', 'col_b', 'col_c'}
            assert 'attachments' not in results[0]['metadata'] # Key should be removed
            assert 'metadata' in results[1]
            assert set(results[1]['metadata'].keys()) == {'col_a', 'col_b', 'col_c'}
        finally:
            # Restore or remove the override
            if original_override is not None:
                app.dependency_overrides[get_validated_token] = original_override
            elif get_validated_token in app.dependency_overrides:
                del app.dependency_overrides[get_validated_token]

@pytest.mark.asyncio
async def test_search_combined_filtering(client: TestClient):
    """Test combination of column projection and attachment disallow."""
    test_token = create_mock_token(allow_columns=['col_b'], allow_attachments=False)
    with patch(f'{SEARCH_SERVICE_PATH}.search_milvus_knowledge', new_callable=AsyncMock) as mock_search,
         patch(f'{SEARCH_SERVICE_PATH}.rerank_results', new_callable=AsyncMock) as mock_rerank,
         patch(f'{SEARCH_SERVICE_PATH}.token_crud.create_milvus_filter_from_token') as mock_filter,
         patch(f'{SEARCH_SERVICE_PATH}.create_embedding', new_callable=AsyncMock) as mock_embed:
        
        mock_search.return_value = [MOCK_SEARCH_RESULTS]
        mock_rerank.return_value = MOCK_SEARCH_RESULTS
        mock_filter.return_value = "mock_filter_expression"
        mock_embed.return_value = [0.1] * 100

        original_override = app.dependency_overrides.get(get_validated_token)
        app.dependency_overrides[get_validated_token] = lambda: test_token
        try:
            headers = {"Authorization": f"Bearer faketokenvalue"}
            response = client.get("/shared-knowledge/search?query=test", headers=headers)
            assert response.status_code == 200
            results = response.json()
            assert len(results) == 2
            assert 'metadata' in results[0]
            assert list(results[0]['metadata'].keys()) == ['col_b']
            assert results[0]['metadata']['col_b'] == 'value_b1'
            assert 'col_a' not in results[0]['metadata']
            assert 'col_c' not in results[0]['metadata']
            assert 'attachments' not in results[0]['metadata']
            assert 'metadata' in results[1]
            assert list(results[1]['metadata'].keys()) == ['col_b']
            assert results[1]['metadata']['col_b'] == 'value_b2'
        finally:
            # Restore or remove the override
            if original_override is not None:
                app.dependency_overrides[get_validated_token] = original_override
            elif get_validated_token in app.dependency_overrides:
                del app.dependency_overrides[get_validated_token]

# Add more tests for edge cases (no allow_columns, allow_attachments=True, etc.) 