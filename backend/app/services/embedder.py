import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from fastapi import HTTPException

from app.config import settings
from app.db.qdrant_client import get_qdrant_client

# Set up logging
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

# Initialize default client using system key
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Modify to accept an optional client
async def create_embedding(text: str, client: Optional[AsyncOpenAI] = None) -> List[float]:
    """Creates an embedding for the given text using the configured embedding model."""
    # Use the provided client if available, otherwise use the default global client
    active_client = client if client else openai_client
    embedding_model_name = settings.EMBEDDING_MODEL # Get model name from settings
    if not embedding_model_name:
        logger.error("EMBEDDING_MODEL setting is not configured in settings.")
        raise ValueError("Embedding model name is not configured.")
        
    try:
        logger.debug(f"Creating embedding using model: {embedding_model_name}")
        response = await active_client.embeddings.create(
            input=[text.replace("\n", " ")], # Replace newlines as recommended by OpenAI
            model=embedding_model_name # Use model name from settings
        )
        return response.data[0].embedding
    except Exception as e:
        # Log the error
        logger.error(f"Error creating embedding: {e}", exc_info=True)
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
    logger.debug(f"Qdrant Query Embedding (first 5 elements): {query_embedding[:5]}...")
    
    logger.debug(f"Attempting Qdrant search in collection '{collection_name}' with limit {limit} and filter {qdrant_filter}")
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
        logger.debug(f"Qdrant search successful. Returning {len(formatted_results)} formatted results.")
        return formatted_results
        
    except UnexpectedResponse as e:
        # Use logger instead of print
        logger.error(f"Qdrant search error (collection: '{collection_name}'): Status={e.status_code}, Response={e.content}", exc_info=True)
        if e.status_code == 404:
             logger.warning(f"Qdrant collection '{collection_name}' not found.")
             return [] # Return empty list if collection doesn't exist
        # Consider raising specific Qdrant exception?
        raise HTTPException(status_code=500, detail=f"Qdrant search failed unexpectedly (collection: '{collection_name}')") 
    except Exception as e:
        # Use logger instead of print
        logger.error(f"Generic error during Qdrant search (collection: '{collection_name}'): {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge base (collection: '{collection_name}'): {str(e)}")
