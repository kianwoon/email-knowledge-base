from typing import List, Dict, Any
from openai import AsyncOpenAI

from app.config import settings

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def create_embedding(text: str) -> List[float]:
    """
    Create an embedding vector for the given text using OpenAI's embedding model
    """
    try:
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text
        )
        
        # Extract the embedding vector
        embedding = response.data[0].embedding
        return embedding
    
    except Exception as e:
        print(f"Error creating embedding: {str(e)}")
        # Return a zero vector as fallback
        return [0.0] * settings.EMBEDDING_DIMENSION


async def search_similar(query_embedding: List[float], limit: int = 10, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Search for similar vectors in Qdrant
    This is a placeholder implementation - in a real app, this would connect to Qdrant
    """
    # In a real implementation, this would search in Qdrant
    # For now, we'll return placeholder results
    results = [
        {
            "id": f"result_{i}",
            "email_id": f"email_{i}",
            "content": f"Sample content for result {i}",
            "metadata": {
                "department": "general",
                "sensitivity": "low",
                "tags": ["sample", "placeholder"],
            },
            "score": 0.9 - (i * 0.1)
        }
        for i in range(min(5, limit))
    ]
    
    return results
