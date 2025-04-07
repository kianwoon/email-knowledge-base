import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Literal
from pydantic import BaseModel

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.db.qdrant_client import get_qdrant_client # Assuming Qdrant client dependency
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
# Import the service function we will create
# from app.services.knowledge_service import fetch_collection_summary 

router = APIRouter()
logger = logging.getLogger("app")

# Define valid collection names using Literal for validation
ValidCollectionName = Literal['email_knowledge', 'email_knowledge_base']

class CollectionSummaryResponseModel(BaseModel):
    count: int

@router.get("/summary/{collection_name}", response_model=CollectionSummaryResponseModel)
async def get_collection_summary_route(
    collection_name: ValidCollectionName, # Use Literal for path param validation
    current_user: User = Depends(get_current_user),
    qdrant: QdrantClient = Depends(get_qdrant_client) # Inject Qdrant client
):
    """Get summary statistics (item count) for a user-specific knowledge collection."""
    # Construct the user-specific collection name AGAIN
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    actual_collection_name = f"{sanitized_email}_{collection_name}"
    logger.info(f"User '{current_user.email}' requesting summary for user-specific collection: {actual_collection_name}")

    # Input validation for base collection_name is handled by FastAPI using Literal type hint
    
    try:
        # --- REMOVED owner filter --- 
        # owner_filter = rest.Filter(
        #     must=[
        #         rest.FieldCondition(
        #             key="owner", # Assuming the payload field is named 'owner'
        #             match=rest.MatchValue(value=current_user.email)
        #         )
        #     ]
        # )
        
        # --- Direct Qdrant Call (Using user-specific collection name, NO filter) ---
        logger.debug(f"Calling qdrant_client.count for user-specific collection: {actual_collection_name}")
        try:
            count_result = qdrant.count(
                collection_name=actual_collection_name, # Use user-specific name
                # count_filter=owner_filter,     # REMOVED owner filter
                exact=True
            )
            logger.debug(f"Qdrant count result: {count_result}")
            summary_data = {"count": count_result.count}
        except UnexpectedResponse as e:
            # If Qdrant returns 404, the user-specific collection doesn't exist
            if e.status_code == 404:
                logger.warning(f"User-specific collection '{actual_collection_name}' not found in Qdrant. Returning count 0.")
                summary_data = {"count": 0}
            else:
                # Re-raise other unexpected Qdrant errors
                raise e 
        # --- End Direct Qdrant Call --- 

        logger.info(f"Successfully retrieved summary for {actual_collection_name}: Count={summary_data.get('count')}")
        return summary_data
    except Exception as e:
        # Catch errors from the try block above (like non-404 Qdrant errors) or other unexpected issues
        logger.error(f"Error fetching summary for user-specific collection {actual_collection_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # Return generic error message to frontend, hiding specific collection name
            detail=f"Failed to retrieve summary for collection {collection_name}."
        ) 