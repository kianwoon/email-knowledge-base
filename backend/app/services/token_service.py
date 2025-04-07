# backend/app/services/token_service.py
import logging
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List, Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import PointStruct, Distance, VectorParams, Filter, FieldCondition, MatchValue, PointIdsList
from qdrant_client.http.exceptions import UnexpectedResponse

from ..config import settings
from ..models.token import Token, TokenCreate, TokenUpdate, TokenPayload, AccessRule

# Configure logging
logger = logging.getLogger(__name__)

TOKEN_COLLECTION_NAME = "knowledge_sharing_tokens"

# --- Helper Function for Dummy Vector ---

def _get_dummy_vector() -> List[float]:
    """ Creates a dummy vector of zeros based on settings. """
    return [0.0] * settings.QDRANT_VECTOR_SIZE

# --- Collection Management ---

def ensure_token_collection(client: QdrantClient):
    """ Ensures the token collection exists in Qdrant. """
    try:
        collection_info = client.get_collection(collection_name=TOKEN_COLLECTION_NAME)
        logger.info(f"Token collection '{TOKEN_COLLECTION_NAME}' already exists.")
    except UnexpectedResponse as e:
        if e.status_code == 404:
            logger.info(f"Token collection '{TOKEN_COLLECTION_NAME}' not found. Creating...")
            try:
                client.create_collection(
                    collection_name=TOKEN_COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=settings.QDRANT_VECTOR_SIZE, 
                        distance=Distance.COSINE # Or settings.QDRANT_DISTANCE_METRIC, match data collections
                    )
                    # Add other configurations like HNSW if needed, consistent with other collections
                )
                logger.info(f"Successfully created token collection '{TOKEN_COLLECTION_NAME}'.")
            except Exception as create_err:
                logger.error(f"Failed to create token collection '{TOKEN_COLLECTION_NAME}': {create_err}", exc_info=True)
                raise
        else:
            logger.error(f"Error checking token collection '{TOKEN_COLLECTION_NAME}': {e}", exc_info=True)
            raise
    except Exception as ex:
        logger.error(f"Unexpected error ensuring token collection '{TOKEN_COLLECTION_NAME}': {ex}", exc_info=True)
        raise

# --- CRUD Operations ---

async def create_token(client: QdrantClient, token_data: TokenCreate, owner_email: str) -> Optional[Token]:
    """ Creates a new token and stores it as a point in Qdrant. """
    try:
        ensure_token_collection(client) # Ensure collection exists first

        token_id = uuid4()
        now = datetime.now(timezone.utc)
        
        # Prepare the full payload including ownership and timestamps
        token_payload_dict = token_data.model_dump()
        token_payload_dict['id'] = token_id
        token_payload_dict['owner_email'] = owner_email
        token_payload_dict['created_at'] = now
        token_payload_dict['updated_at'] = now

        # Validate payload with the model (optional but good practice)
        token_payload_obj = TokenPayload(**token_payload_dict)

        point = PointStruct(
            id=str(token_id), # Qdrant ID must be string or int
            vector=_get_dummy_vector(),
            payload=token_payload_obj.model_dump(mode='json') # Store as dict
        )

        client.upsert(
            collection_name=TOKEN_COLLECTION_NAME,
            points=[point],
            wait=True
        )
        logger.info(f"Successfully created token {token_id} for owner {owner_email}.")
        # Return the full Token object corresponding to the created payload
        return Token(**token_payload_obj.model_dump())

    except Exception as e:
        logger.error(f"Failed to create token for owner {owner_email}: {e}", exc_info=True)
        return None

async def get_token_by_id(client: QdrantClient, token_id: UUID) -> Optional[Token]:
    """ Retrieves a token by its ID from Qdrant. """
    try:
        # Qdrant uses string representation of UUID for point IDs
        point_id_str = str(token_id)
        result = client.retrieve(
            collection_name=TOKEN_COLLECTION_NAME,
            ids=[point_id_str],
            with_payload=True
        )

        if not result:
            logger.warning(f"Token with ID {token_id} not found.")
            return None
        
        # Assuming the ID is unique, we expect at most one point
        point_data = result[0].payload
        if not point_data:
             logger.warning(f"Token point {token_id} found but has no payload.")
             return None
        
        # Reconstruct the Token object from the payload
        return Token(**point_data)

    except Exception as e:
        logger.error(f"Failed to retrieve token {token_id}: {e}", exc_info=True)
        return None

async def list_tokens_by_owner(client: QdrantClient, owner_email: str) -> List[Token]:
    """ Lists all tokens owned by a specific user. """
    tokens: List[Token] = []
    try:
        scroll_filter = Filter(
            must=[
                FieldCondition(
                    key="owner_email",
                    match=MatchValue(value=owner_email)
                )
            ]
        )

        # Use scroll API to get all matching points
        offset = None
        while True:
            results, next_offset = client.scroll(
                collection_name=TOKEN_COLLECTION_NAME,
                scroll_filter=scroll_filter,
                limit=100, # Adjust limit as needed
                offset=offset,
                with_payload=True
            )
            
            for point in results:
                if point.payload:
                    try:
                        tokens.append(Token(**point.payload))
                    except Exception as parse_err:
                         logger.warning(f"Failed to parse token payload for point {point.id}: {parse_err}", exc_info=True)
            
            if next_offset is None:
                break # No more points to fetch
            offset = next_offset
            
        logger.info(f"Found {len(tokens)} tokens for owner {owner_email}.")
        return tokens

    except Exception as e:
        logger.error(f"Failed to list tokens for owner {owner_email}: {e}", exc_info=True)
        return [] # Return empty list on error

async def update_token(client: QdrantClient, token_id: UUID, update_data: TokenUpdate, owner_email: str) -> Optional[Token]:
    """ Updates an existing token in Qdrant. """
    try:
        point_id_str = str(token_id)
        # 1. Retrieve the current token
        current_token_point = client.retrieve(
            collection_name=TOKEN_COLLECTION_NAME,
            ids=[point_id_str],
            with_payload=True
        )

        if not current_token_point:
            logger.warning(f"Update failed: Token {token_id} not found.")
            return None
        
        current_payload_dict = current_token_point[0].payload
        if not current_payload_dict:
            logger.warning(f"Update failed: Token {token_id} has no payload.")
            return None
        
        # Use TokenPayload for validation and structure
        current_token_obj = TokenPayload(**current_payload_dict)

        # 2. Authorization Check
        if current_token_obj.owner_email != owner_email:
            logger.error(f"Authorization failed: User {owner_email} cannot update token {token_id} owned by {current_token_obj.owner_email}.")
            return None # Or raise HTTPException(status_code=403)
        
        # 3. Check if editable
        if not current_token_obj.is_editable:
             logger.warning(f"Update failed: Token {token_id} is not editable.")
             return None # Or raise HTTPException(status_code=400)

        # 4. Apply updates
        update_dict = update_data.model_dump(exclude_unset=True) # Get only provided fields
        if not update_dict:
             logger.warning(f"Update request for token {token_id} had no fields to update.")
             return Token(**current_token_obj.model_dump()) # Return current token if no updates

        # Create the updated object by merging
        updated_token_data = current_token_obj.model_copy(update=update_dict)
        
        # Update the timestamp
        updated_token_data.updated_at = datetime.now(timezone.utc)
        
        # 5. Upsert the updated point
        updated_point = PointStruct(
            id=point_id_str,
            vector=_get_dummy_vector(),
            payload=updated_token_data.model_dump(mode='json')
        )

        client.upsert(
            collection_name=TOKEN_COLLECTION_NAME,
            points=[updated_point],
            wait=True
        )

        logger.info(f"Successfully updated token {token_id} for owner {owner_email}.")
        # Return the updated Token object
        return Token(**updated_token_data.model_dump())

    except Exception as e:
        logger.error(f"Failed to update token {token_id}: {e}", exc_info=True)
        return None

async def delete_token(client: QdrantClient, token_id: UUID, owner_email: str) -> bool:
    """ Deletes a token from Qdrant after verifying ownership. """
    try:
        point_id_str = str(token_id)
        # 1. Retrieve the current token to verify ownership
        current_token_point = client.retrieve(
            collection_name=TOKEN_COLLECTION_NAME,
            ids=[point_id_str],
            with_payload=True # Need payload for owner check
        )

        if not current_token_point:
            logger.warning(f"Delete failed: Token {token_id} not found.")
            return False # Token doesn't exist
            
        current_payload = current_token_point[0].payload
        if not current_payload or current_payload.get('owner_email') != owner_email:
            logger.error(f"Authorization failed: User {owner_email} cannot delete token {token_id}.")
            # Optionally check if payload exists but owner doesn't match
            if current_payload and current_payload.get('owner_email'):
                 logger.error(f"Token owned by {current_payload.get('owner_email')}.")
            return False # Authorization failed or bad data

        # 2. Delete the point
        client.delete(
            collection_name=TOKEN_COLLECTION_NAME,
            points_selector=PointIdsList(points=[point_id_str]),
            wait=True
        )
        logger.info(f"Successfully deleted token {token_id} by owner {owner_email}.")
        return True

    except Exception as e:
        logger.error(f"Failed to delete token {token_id}: {e}", exc_info=True)
        return False 