from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from fastapi import HTTPException

from app.config import settings
from app.db.qdrant_client import get_qdrant_client

# Initialize default client using system key
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Modify to accept an optional client
async def create_embedding(text: str, client: Optional[AsyncOpenAI] = None) -> List[float]:
    """Creates an embedding for the given text using OpenAI's text-embedding-3-small model."""
    # Use the provided client if available, otherwise use the default global client
    active_client = client if client else openai_client
    try:
        response = await active_client.embeddings.create(
            input=[text], 
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    except Exception as e:
        # Log the error
        print(f"Error creating embedding: {e}")
        # Re-raise or handle as appropriate, e.g., return None or raise specific exception
        raise

# Renamed placeholder search_similar and implemented real search
async def search_qdrant_knowledge(
    query_embedding: List[float], 
    limit: int = 3, 
    collection_name: str = settings.QDRANT_COLLECTION_NAME, # Default collection, can be overridden
    qdrant_filter: Optional[models.Filter] = None
) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in the specified Qdrant collection.
    Returns a list of results including payload.
    """
    qdrant_client: QdrantClient = get_qdrant_client()
    
    try:
        search_result = qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True # Crucial to get the text content
        )
        
        # Format results (or return raw ScoredPoint objects)
        formatted_results = [
            {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload # Include the full payload
            }
            for hit in search_result
        ]
        return formatted_results
        
    except UnexpectedResponse as e:
        print(f"Qdrant search error (collection: {collection_name}): {e}")
        # Handle cases like collection not found, etc.
        if e.status_code == 404:
             print(f"Collection '{collection_name}' not found.")
             return [] # Return empty list if collection doesn't exist
        raise HTTPException(status_code=500, detail=f"Qdrant search failed: {e}") # Re-raise for other Qdrant errors
    except Exception as e:
        print(f"Generic error during Qdrant search (collection: {collection_name}): {e}")
        # Log the full error details
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge base: {e}") # Re-raise generic errors
