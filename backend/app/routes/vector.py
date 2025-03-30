from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.models.email import EmailVectorData, ReviewStatus
from app.models.user import User
from app.routes.auth import get_current_user
from app.services.embedder import create_embedding, search_similar
from app.config import settings

router = APIRouter()


@router.post("/embed", response_model=EmailVectorData)
async def embed_email(
    email_id: str,
    content: str,
    metadata: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Create embedding for approved email content and store in vector database"""
    # Generate embedding
    try:
        embedding = await create_embedding(content)
        
        # Create vector data object
        vector_data = EmailVectorData(
            id=f"vec_{email_id}",
            email_id=email_id,
            content=content,
            metadata=metadata,
            embedding=embedding,
            created_at=datetime.now()
        )
        
        # In a real implementation, this would store the vector in Qdrant
        # For now, we'll just return the vector data object
        return vector_data
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create embedding: {str(e)}"
        )


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_vectors(
    query: str,
    limit: int = Query(10, ge=1, le=100),
    department: Optional[str] = None,
    sensitivity: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Search for similar vectors using semantic search"""
    try:
        # Generate embedding for the query
        query_embedding = await create_embedding(query)
        
        # Search for similar vectors
        # In a real implementation, this would search in Qdrant
        # For now, we'll return a placeholder result
        results = [
            {
                "id": f"result_{i}",
                "email_id": f"email_{i}",
                "content": f"Sample content for result {i}",
                "metadata": {
                    "department": department or "general",
                    "sensitivity": sensitivity or "low",
                    "tags": ["sample", "placeholder"],
                    "created_at": datetime.now().isoformat()
                },
                "score": 0.9 - (i * 0.1)
            }
            for i in range(min(5, limit))
        ]
        
        return results
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.delete("/{vector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vector(
    vector_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a vector from the database"""
    # In a real implementation, this would delete the vector from Qdrant
    # For now, we'll just return a success response
    return None
