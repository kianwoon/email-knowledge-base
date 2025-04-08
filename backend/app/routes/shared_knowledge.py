import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client import models as qdrant_models
from datetime import datetime, timezone
import bcrypt

from ..db.session import get_db
from ..db.qdrant_client import get_qdrant_client # Using the existing dependency
from ..models.token_models import TokenDB
from ..crud import token_crud
from ..services.embedder import create_embedding 

# Configure logging
logger = logging.getLogger(__name__)

# API Key Header for Bearer token
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# --- Token Validation Dependency ---

async def get_validated_token(
    authorization: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db)
) -> TokenDB:
    """
    Validates the Bearer token from the Authorization header.
    Checks hash, active status, and expiry.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if authorization is None or not authorization.lower().startswith("bearer "):
        logger.debug("Authorization header missing or not Bearer")
        raise credentials_exception

    token_value = authorization.split(" ", 1)[1]
    if not token_value:
        logger.debug("Bearer token value missing")
        raise credentials_exception

    # Fetch token by comparing hashes (logic from existing crud.get_token_by_value)
    db_token = token_crud.get_token_by_value(db, token_value)

    if db_token is None:
        logger.debug(f"Token not found for value: {token_value[:5]}...{token_value[-5:]}")
        raise credentials_exception

    # Check if token is active and not expired
    now = datetime.now(timezone.utc)
    is_expired = db_token.expiry is not None and db_token.expiry <= now
    if not db_token.is_active or is_expired:
        logger.warning(f"Token {db_token.id} is inactive or expired.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Token is inactive or expired"
        )

    logger.info(f"Successfully validated token {db_token.id} for owner {db_token.owner_email}")
    return db_token

# --- Router Definition ---

router = APIRouter(
    prefix="/shared-knowledge",
    tags=["Shared Knowledge"],
    responses={404: {"description": "Not found"}},
)

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_shared_knowledge(
    query: str = Query(..., description="The search query string."),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return."),
    token: TokenDB = Depends(get_validated_token), # Use the dependency to get the validated token
    qdrant: QdrantClient = Depends(get_qdrant_client) # Use existing Qdrant client dependency
):
    """
    Performs a semantic search on the knowledge base using a valid API token.
    Access is controlled by the rules and sensitivity defined in the token.
    """
    logger.info(f"Shared search request received using token {token.id} (Owner: {token.owner_email}), Query: '{query}'")

    try:
        # 1. Determine target collection based on token owner
        sanitized_email = token.owner_email.replace('@', '_').replace('.', '_')
        # Construct the collection name as owner_email_knowledge_base
        target_collection_name = f"{sanitized_email}_knowledge_base"
        logger.info(f"Targeting search in collection: {target_collection_name} based on token owner.")

        # 2. Generate embedding for the query
        query_embedding = await create_embedding(query)
        if not query_embedding:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate query embedding.")

        # 3. Generate Qdrant filter based on token rules
        qdrant_filter = token_crud.create_qdrant_filter_from_token(token)
        logger.debug(f"Generated Qdrant filter for token {token.id}: {qdrant_filter}")

        # 4. Perform the search
        search_result = qdrant.search(
            collection_name=target_collection_name,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True  # Include payload/metadata in results
        )
        
        # 5. Format results (Extract payload and score)
        results = []
        for hit in search_result:
            results.append({
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload
            })
            
        logger.info(f"Found {len(results)} results for query '{query}' using token {token.id}.")
        return results

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions (like embedding failure)
        raise http_exc
    except Exception as e:
        logger.error(f"Error during shared knowledge search for token {token.id}: {e}", exc_info=True)
        # Check if the collection was not found
        if "not found" in str(e).lower() and target_collection_name in str(e):
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Knowledge base collection for token owner not found.")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during the search.") 