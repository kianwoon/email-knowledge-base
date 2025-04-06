from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import logging

# Qdrant imports
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue

from app.models.email import EmailVectorData, ReviewStatus
from app.models.user import User
from app.routes.auth import get_current_user
from app.services.embedder import create_embedding, search_similar
from app.config import settings
# Import Qdrant client functions
from app.db.qdrant_client import get_qdrant_client, ensure_collection_exists

router = APIRouter()
logger = logging.getLogger("app")

# Dependency to get Qdrant client and ensure collection exists
async def get_db() -> QdrantClient:
    client = get_qdrant_client()
    # Ensure collection exists on first request (or use FastAPI startup event)
    # Using a simple flag here, consider a more robust approach for production
    if not getattr(get_db, "collection_checked", False):
        ensure_collection_exists(client)
        setattr(get_db, "collection_checked", True) 
    return client

@router.post("/embed", response_model=Dict[str, Any]) # Return a simple status dict
async def embed_email(
    email_id: str, # Should be provided by the caller (e.g., from review step)
    content: str, # Email body
    metadata: Dict[str, Any], # Metadata from qdrant_email_knowledge_schema.md
    current_user: User = Depends(get_current_user),
    client: QdrantClient = Depends(get_db)
):
    """Create embedding for approved email content and store in vector database"""
    logger.info(f"Received request to embed email ID: {email_id} for owner: {current_user.email}")

    # Validate required metadata (as per schema doc)
    required_meta = ['owner', 'sender', 'subject', 'date', 'has_attachments', 'folder', 'tags', 'analysis_status', 'status', 'source', 'raw_text']
    if not all(key in metadata for key in required_meta):
        missing_keys = [key for key in required_meta if key not in metadata]
        logger.error(f"Missing required metadata keys: {missing_keys}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required metadata keys: {missing_keys}"
        )

    # Ensure owner matches current user for security
    if metadata.get('owner') != current_user.email:
         logger.error(f"Metadata owner '{metadata.get('owner')}' does not match authenticated user '{current_user.email}'")
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Cannot embed email for a different owner."
         )

    # Generate embedding
    try:
        embedding = await create_embedding(content) # Use the existing embedder service
    except Exception as e:
        logger.error(f"Failed to create embedding for email ID {email_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create embedding: {str(e)}"
        )

    # Prepare point for Qdrant
    point_id = str(uuid.uuid4()) # Generate a unique ID for the point
    point = PointStruct(
        id=point_id,
        vector=embedding,
        payload=metadata # Use the provided metadata directly
    )

    # Upsert into Qdrant
    try:
        logger.info(f"Upserting point ID {point_id} into collection '{settings.QDRANT_COLLECTION_NAME}'")
        client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[point],
            wait=True # Wait for operation to complete
        )
        logger.info(f"Successfully upserted point ID {point_id}")
        return {"status": "success", "vector_id": point_id, "email_id": email_id}
    except Exception as e:
        logger.error(f"Failed to upsert point ID {point_id} into Qdrant: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store vector in database: {str(e)}"
        )

@router.get("/search", response_model=List[Dict[str, Any]])
async def search_vectors(
    query: str,
    limit: int = Query(10, ge=1, le=100),
    # Add filters based on metadata schema
    folder: Optional[str] = None,
    tags: Optional[List[str]] = Query(None), # Allow multiple tags
    status_filter: Optional[str] = Query(None, alias="status"), # Use alias for reserved word
    start_date: Optional[str] = None, # YYYY-MM-DD
    end_date: Optional[str] = None, # YYYY-MM-DD
    current_user: User = Depends(get_current_user),
    client: QdrantClient = Depends(get_db)
):
    """Search for similar vectors using semantic search with filtering."""
    logger.info(f"Received search request: '{query}' for owner: {current_user.email}")
    try:
        # Generate embedding for the query
        query_embedding = await create_embedding(query)

        # Build Qdrant filters based on query parameters
        qdrant_filter = models.Filter(must=[])

        # ALWAYS filter by owner
        qdrant_filter.must.append(models.FieldCondition(key="owner", match=models.MatchValue(value=current_user.email)))

        if folder:
            qdrant_filter.must.append(models.FieldCondition(key="folder", match=models.MatchValue(value=folder)))
        
        if tags:
            # Assuming tags need to match ALL provided tags - use multiple conditions
            for tag in tags:
                 qdrant_filter.must.append(models.FieldCondition(key="tags", match=models.MatchValue(value=tag)))
            # Alternative: Check if payload field contains ANY of the tags (might require different indexing/query)

        if status_filter:
             qdrant_filter.must.append(models.FieldCondition(key="status", match=models.MatchValue(value=status_filter)))

        # Add date range filter if needed (requires date field to be indexed appropriately, e.g., as timestamp or string YYYY-MM-DD)
        # Note: Qdrant range filter works best with numerical timestamps. 
        # If using string dates, lexicographical comparison applies.
        range_conditions = {}
        if start_date:
             # Assuming date is stored as YYYY-MM-DD string
             range_conditions['gte'] = start_date 
        if end_date:
             range_conditions['lte'] = end_date
        if range_conditions:
             qdrant_filter.must.append(models.FieldCondition(key="date", range=models.Range(**range_conditions)))
             
        logger.debug(f"Constructed Qdrant filter: {qdrant_filter.model_dump_json()}")

        # Search Qdrant
        search_result = client.search(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True # Include metadata in results
        )

        # Format results
        formatted_results = [
            {
                "id": hit.id,
                "score": hit.score,
                "metadata": hit.payload
                # "content": hit.payload.get("raw_text", "") # Optionally include raw text
            }
            for hit in search_result
        ]
        logger.info(f"Search completed. Found {len(formatted_results)} results.")
        return formatted_results

    except Exception as e:
        logger.error(f"Search failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )

@router.delete("/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vector(
    point_id: str, # Use the Qdrant point ID
    current_user: User = Depends(get_current_user),
    client: QdrantClient = Depends(get_db)
):
    """Delete a vector point from Qdrant, ensuring owner match."""
    logger.info(f"Received request to delete point ID: {point_id} for owner: {current_user.email}")
    try:
        # Optional but recommended: Retrieve the point first to verify owner
        retrieve_result = client.retrieve(collection_name=settings.QDRANT_COLLECTION_NAME, ids=[point_id], with_payload=True)
        if not retrieve_result:
            logger.warning(f"Point ID {point_id} not found for deletion.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vector point not found.")
        
        point_payload = retrieve_result[0].payload
        if point_payload.get("owner") != current_user.email:
            logger.error(f"Attempt to delete point {point_id} belonging to owner {point_payload.get('owner')} by user {current_user.email}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete vector point belonging to another user.")
        
        # Delete the point
        client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=models.PointIdsList(points=[point_id]),
            wait=True
        )
        logger.info(f"Successfully deleted point ID: {point_id}")
        return None # Return None for 204 No Content response

    except HTTPException as http_exc: # Re-raise specific HTTP exceptions
        raise http_exc
    except Exception as e:
        logger.error(f"Failed to delete point ID {point_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vector: {str(e)}"
        )
