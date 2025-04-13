import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone # Import datetime

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

# Response model for the existing single collection summary endpoint
class CollectionSummaryResponseModel(BaseModel):
    count: int

# NEW: Response model for the combined knowledge base summary
class KnowledgeSummaryResponseModel(BaseModel):
    raw_data_count: int # Email raw data
    sharepoint_raw_data_count: int # SharePoint raw data
    vector_data_count: int
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

# NEW: Endpoint for combined knowledge base summary
@router.get("/summary", response_model=KnowledgeSummaryResponseModel)
async def get_knowledge_summary_route(
    current_user: User = Depends(get_current_user),
    qdrant: QdrantClient = Depends(get_qdrant_client)
):
    """Get combined summary statistics (item counts) for user's knowledge collections."""
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    # Collection for EMAIL raw data items
    email_raw_collection_name = f"{sanitized_email}_email_knowledge"
    # Collection for SHAREPOINT raw data items
    sharepoint_raw_collection_name = f"{sanitized_email}_sharepoint_knowledge"
    # Collection for vector data (RAG)
    vector_collection_name = f"{sanitized_email}_knowledge_base"
    logger.info(f"User '{current_user.email}' requesting combined knowledge summary for collections: {email_raw_collection_name}, {sharepoint_raw_collection_name}, {vector_collection_name}")

    email_raw_count = 0
    sharepoint_raw_count = 0
    vector_count = 0
    last_update_time = None # Placeholder for last update time if needed

    try:
        # Get EMAIL raw data count
        try:
            logger.debug(f"Calling qdrant_client.count for EMAIL raw data collection: {email_raw_collection_name}")
            count_result_raw = qdrant.count(collection_name=email_raw_collection_name, exact=True)
            email_raw_count = count_result_raw.count
            logger.debug(f"EMAIL raw data count for {email_raw_collection_name}: {email_raw_count}")
            # Potentially get last update time here if Qdrant provides it easily
        except UnexpectedResponse as e:
            if e.status_code == 404:
                logger.warning(f"EMAIL raw data collection '{email_raw_collection_name}' not found. Setting count to 0.")
                email_raw_count = 0
            else:
                logger.error(f"Qdrant error counting {email_raw_collection_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error accessing email raw data storage.")

        # Get SHAREPOINT raw data count
        try:
            logger.debug(f"Calling qdrant_client.count for SHAREPOINT raw data collection: {sharepoint_raw_collection_name}")
            count_result_sharepoint = qdrant.count(collection_name=sharepoint_raw_collection_name, exact=True)
            sharepoint_raw_count = count_result_sharepoint.count
            logger.debug(f"SHAREPOINT raw data count for {sharepoint_raw_collection_name}: {sharepoint_raw_count}")
             # Potentially get last update time here too
        except UnexpectedResponse as e:
            if e.status_code == 404:
                logger.warning(f"SHAREPOINT raw data collection '{sharepoint_raw_collection_name}' not found. Setting count to 0.")
                sharepoint_raw_count = 0
            else:
                logger.error(f"Qdrant error counting {sharepoint_raw_collection_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error accessing SharePoint raw data storage.")

        # Get vector data count
        try:
            logger.debug(f"Calling qdrant_client.count for vector data collection: {vector_collection_name}")
            count_result_vector = qdrant.count(collection_name=vector_collection_name, exact=True)
            vector_count = count_result_vector.count
            logger.debug(f"Vector data count for {vector_collection_name}: {vector_count}")
            # Update last_update_time if vector collection exists and has info
            try:
                collection_info = qdrant.get_collection(collection_name=vector_collection_name)
                # Assuming Qdrant might store some update time metadata, adjust as needed
                # This part is speculative based on Qdrant features
                # last_update_time = collection_info.get('last_updated', datetime.now(timezone.utc))
                pass # If no specific update time available, keep default
            except Exception: # Catch potential errors getting collection info
                 logger.warning(f"Could not get collection info for {vector_collection_name} to determine last update time.")
                 pass

        except UnexpectedResponse as e:
            if e.status_code == 404:
                logger.warning(f"Vector data collection '{vector_collection_name}' not found. Setting count to 0.")
                vector_count = 0
            else:
                logger.error(f"Qdrant error counting {vector_collection_name}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error accessing vector data storage.")

        logger.info(f"Successfully retrieved combined summary for '{current_user.email}': EmailRaw={email_raw_count}, SharePointRaw={sharepoint_raw_count}, Vector={vector_count}")
        # Return counts including SharePoint raw data
        return KnowledgeSummaryResponseModel(
            raw_data_count=email_raw_count,
            sharepoint_raw_data_count=sharepoint_raw_count,
            vector_data_count=vector_count,
            last_updated=last_update_time if last_update_time else datetime.now(timezone.utc) # Use fetched or default time
        )

    except Exception as e:
        logger.error(f"Unexpected error fetching combined summary for user '{current_user.email}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the knowledge base summary."
        ) 