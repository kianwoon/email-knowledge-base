import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Literal, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone # Import datetime

# Milvus imports (replacing Qdrant)
from pymilvus import MilvusClient
# from qdrant_client import QdrantClient
# from qdrant_client.http.exceptions import UnexpectedResponse
# from qdrant_client.http.models import PointStruct # Keep for now, replace later

from app.dependencies.auth import get_current_user
from app.models.user import User
# Import Milvus client (replacing Qdrant)
from app.db.milvus_client import get_milvus_client
# from app.db.qdrant_client import get_qdrant_client # Assuming Qdrant client dependency

from app.config import settings
import uuid
from app.services.embedder import create_embedding

# Import the service function we will create
# from app.services.knowledge_service import fetch_collection_summary 

# +++ Import SQL Session and CRUD +++
from sqlalchemy.orm import Session
from app.db.session import get_db # Corrected import name
from app.crud import crud_processed_file
# --- End Import ---

# --- ADDED: Iceberg Imports ---
import pandas as pd
from pyiceberg.catalog import load_catalog, Catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError
from pyiceberg.expressions import EqualTo
# --- END: Iceberg Imports ---

router = APIRouter()
logger = logging.getLogger("app")

# Define valid collection names using Literal for validation
# TODO: Update this based on Milvus collections if needed
ValidCollectionName = Literal['email_knowledge', 'email_knowledge_base']

# Response model for the existing single collection summary endpoint
class CollectionSummaryResponseModel(BaseModel):
    count: int
    # Add other relevant summary fields as needed
    # e.g., last_updated: Optional[datetime] = None

# Combined response model for all collections
class AllCollectionsSummaryResponseModel(BaseModel):
    # Using Dict where key is collection name, value is summary
    collections: Dict[ValidCollectionName, CollectionSummaryResponseModel]

# Placeholder Request model for adding text
class AddTextRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None
    # Add collection name if needed, or derive from user/context
    collection_name: Optional[ValidCollectionName] = None 

# Placeholder Response model for adding text
class AddTextResponse(BaseModel):
    id: str
    status: str

# NEW: Response model for the combined knowledge base summary
class KnowledgeSummaryResponseModel(BaseModel):
    raw_data_count: int # Email raw data
    email_facts_count: int # ADDED: Count from Iceberg email_facts table
    sharepoint_raw_data_count: int # SharePoint raw data
    s3_raw_data_count: int # S3 raw data
    azure_blob_raw_data_count: int # Azure Blob raw data
    custom_raw_data_count: int # Custom raw data
    vector_data_count: int
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Request model for snippet ingestion
class SnippetRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = {}

# --- ADDED: Iceberg Helper Function (Minimal Implementation) ---
# Ideally, move this to a dedicated service/CRUD file
# Caching can be added here for performance
_iceberg_catalog_instance: Catalog | None = None

def get_iceberg_catalog_cached() -> Catalog | None:
    """Initializes and returns a cached Iceberg catalog instance."""
    global _iceberg_catalog_instance
    if _iceberg_catalog_instance is None:
        try:
            logger.info("Initializing Iceberg REST Catalog for summary...")
            catalog_props = {
                "name": settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_summary_api",
                "uri": settings.R2_CATALOG_URI,
                "warehouse": settings.R2_CATALOG_WAREHOUSE,
                "token": settings.R2_CATALOG_TOKEN,
            }
            catalog_props = {k: v for k, v in catalog_props.items() if v is not None}
            _iceberg_catalog_instance = load_catalog(**catalog_props)
            logger.info("Iceberg Catalog initialized successfully for summary.")
        except Exception as e:
            logger.error(f"Failed to initialize Iceberg Catalog for summary: {e}", exc_info=True)
            _iceberg_catalog_instance = None # Ensure it's None on failure
    return _iceberg_catalog_instance

def get_email_facts_count(owner_email: str) -> int:
    """Counts records in email_facts table for a specific owner."""
    catalog = get_iceberg_catalog_cached()
    if not catalog:
        logger.warning("Cannot count email facts, Iceberg catalog not available.")
        return 0

    full_table_name = f"{settings.ICEBERG_DEFAULT_NAMESPACE}.{settings.ICEBERG_EMAIL_FACTS_TABLE}"
    count = 0
    try:
        logger.debug(f"Attempting to load Iceberg table '{full_table_name}' to count facts for {owner_email}")
        table = catalog.load_table(full_table_name)
        owner_filter = EqualTo("owner_email", owner_email)
        # Scan minimal data with filter
        filtered_scan = table.scan(row_filter=owner_filter, selected_fields=("owner_email",))
        # Efficiently count rows (converting to pandas just for len is okay for moderate counts)
        count = len(filtered_scan.to_pandas())
        logger.debug(f"Found {count} email facts records for {owner_email} in '{full_table_name}'.")
    except (NoSuchTableError, NoSuchNamespaceError):
        logger.warning(f"Iceberg table '{full_table_name}' not found while counting facts for {owner_email}. Returning 0.")
        count = 0
    except Exception as e:
        logger.error(f"Error counting email facts in '{full_table_name}' for {owner_email}: {e}", exc_info=True)
        count = 0 # Default to 0 on error
    return count
# --- END: Iceberg Helper Function ---

@router.get("/summary/{collection_name}", response_model=CollectionSummaryResponseModel)
async def get_collection_summary_route(
    collection_name: ValidCollectionName, # Use Literal for path param validation
    current_user: User = Depends(get_current_user),
    vector_db_client: MilvusClient = Depends(get_milvus_client) # Updated dependency
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
            # Ensure collection is loaded before getting stats
            if vector_db_client.has_collection(collection_name=actual_collection_name) and not vector_db_client.get_load_state(collection_name=actual_collection_name).get("state", "") == "Loaded":
                logger.info(f"Loading collection {actual_collection_name} into memory for stats...")
                vector_db_client.load_collection(collection_name=actual_collection_name)
            
            count_result = vector_db_client.count(
                collection_name=actual_collection_name, # Use user-specific name
                # count_filter=owner_filter,     # REMOVED owner filter
                exact=True
            )
            logger.debug(f"Qdrant count result: {count_result}")
            summary_data = {"count": count_result.count}
        except Exception as e:
            # If Qdrant returns 404, the user-specific collection doesn't exist
            if isinstance(e, ValueError) and "collection not found" in str(e):
                logger.warning(f"User-specific collection '{actual_collection_name}' not found in Milvus. Returning count 0.")
                summary_data = {"count": 0}
            else:
                # Re-raise other unexpected Milvus errors
                raise e 
        # --- End Direct Qdrant Call --- 

        logger.info(f"Successfully retrieved summary for {actual_collection_name}: Count={summary_data.get('count')}")
        return summary_data
    except Exception as e:
        # Catch errors from the try block above (like non-404 Milvus errors) or other unexpected issues
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
    vector_db_client: MilvusClient = Depends(get_milvus_client),
    db: Session = Depends(get_db) # Use the correct dependency function
):
    """Get combined summary statistics (item counts) for user's knowledge collections and processed files."""
    sanitized_email = current_user.email.replace('@', '_').replace('.', '_')
    # Collection for EMAIL raw data items - REMOVED as we now use DB
    # email_raw_collection_name = f"{sanitized_email}_email_knowledge"
    # Collection for SHAREPOINT raw data items
    sharepoint_raw_collection_name = f"{sanitized_email}_sharepoint_knowledge"
    # Collection for S3 raw data items - Use corrected name
    s3_raw_collection_name = f"{sanitized_email}_aws_s3_knowledge" # CORRECTED NAME
    # Collection for AZURE BLOB raw data items
    azure_blob_raw_collection_name = f"{sanitized_email}_azure_blob_knowledge"
    # Collection for CUSTOM KNOWLEDGE raw data items
    custom_knowledge_collection_name = f"{sanitized_email}_custom_knowledge"
    # Collection for vector data (RAG)
    vector_collection_name = f"{sanitized_email}_knowledge_base_bm" # CORRECTED NAME
    
    # Log all collections being queried (adjust log message if needed)
    logger.info(f"User '{current_user.email}' requesting combined knowledge summary from DB, Iceberg, and Milvus for collections: {custom_knowledge_collection_name}, {vector_collection_name}")

    email_raw_count = 0 # Initialize Email count (will come from DB)
    email_facts_count = 0 # ADDED: Iceberg email facts count
    sharepoint_raw_count = 0
    s3_raw_count = 0 # Initialize S3 count
    azure_blob_raw_count = 0 # Initialize Azure Blob count
    custom_raw_count = 0 # Initialize Custom count (will come from Milvus)
    vector_count = 0
    last_update_time = None # Placeholder, DB doesn't track this globally yet

    try:
        # --- REMOVED Milvus query for EMAIL raw data --- 
        # --- Get counts from ProcessedFiles table --- 
        try:
            logger.info(f"Querying ProcessedFiles table for counts for owner {current_user.email}")
            email_raw_count = crud_processed_file.count_processed_files_by_source(db=db, owner_email=current_user.email, source_type='email_attachment') # Get email count from DB
            sharepoint_raw_count = crud_processed_file.count_processed_files_by_source(db=db, owner_email=current_user.email, source_type='sharepoint')
            s3_raw_count = crud_processed_file.count_processed_files_by_source(db=db, owner_email=current_user.email, source_type='s3')
            azure_blob_raw_count = crud_processed_file.count_processed_files_by_source(db=db, owner_email=current_user.email, source_type='azure_blob')
            # --- ADDED: Query for custom_upload source type --- 
            custom_raw_count = crud_processed_file.count_processed_files_by_source(db=db, owner_email=current_user.email, source_type='custom_upload') 
            # --- End Added --- 
            logger.info(f"ProcessedFiles counts - Email: {email_raw_count}, SharePoint: {sharepoint_raw_count}, S3: {s3_raw_count}, Azure Blob: {azure_blob_raw_count}, Custom: {custom_raw_count}") # Updated log
        except Exception as db_err:
            logger.error(f"Error querying ProcessedFiles table counts for owner {current_user.email}: {db_err}", exc_info=True)
            # Set counts to 0 but don't raise HTTPException, allow other counts to proceed
            email_raw_count = 0 # Set email count to 0 on DB error
            sharepoint_raw_count = 0
            s3_raw_count = 0
            azure_blob_raw_count = 0
            custom_raw_count = 0 # Also set custom count to 0 on error
            
        # --- ADDED: Get count from Iceberg email_facts table ---
        email_facts_count = get_email_facts_count(owner_email=current_user.email)
        logger.info(f"Iceberg email_facts count for {current_user.email}: {email_facts_count}")
        # --- END: Get count from Iceberg --- 

        # --- REMOVED Milvus query for CUSTOM raw data count --- 
        # This was overwriting the correct count from the ProcessedFiles table.
        # The custom_raw_count obtained from the DB query above is now used directly.
        # ------------------------------------------------------

        # Get VECTOR data count from Milvus (assuming this is the RAG collection)
        try:
            # Ensure collection is loaded before getting stats
            if vector_db_client.has_collection(collection_name=vector_collection_name) and not vector_db_client.get_load_state(collection_name=vector_collection_name).get("state", "") == "Loaded":
                logger.info(f"Loading collection {vector_collection_name} into memory for stats...")
                vector_db_client.load_collection(collection_name=vector_collection_name)
            
            logger.debug(f"Calling MilvusClient.get_collection_stats for VECTOR data collection: {vector_collection_name}")
            stats_vector = vector_db_client.get_collection_stats(collection_name=vector_collection_name)
            vector_count = int(stats_vector.get('row_count', 0))
            logger.debug(f"VECTOR data count for {vector_collection_name}: {vector_count}")
        except Exception as e:
            if "collection not found" in str(e).lower() or "doesn't exist" in str(e).lower():
                logger.warning(f"VECTOR data collection '{vector_collection_name}' not found. Setting count to 0.")
                vector_count = 0
            else:
                logger.error(f"Milvus error getting stats for {vector_collection_name}: {e}")
                # Log the error but don't raise, return counts obtained so far
                vector_count = 0
        
        # Construct the response
        response_data = KnowledgeSummaryResponseModel(
            raw_data_count=email_raw_count, # Use count from DB
            email_facts_count=email_facts_count, # ADDED: Iceberg count
            sharepoint_raw_data_count=sharepoint_raw_count, # Use count from DB
            s3_raw_data_count=s3_raw_count, # Use count from DB
            azure_blob_raw_data_count=azure_blob_raw_count, # Use count from DB
            custom_raw_data_count=custom_raw_count, # Keep custom count from Milvus (if applicable)
            vector_data_count=vector_count,
            last_updated=datetime.now(timezone.utc) # Use current time as last updated
        )
        logger.info(f"Returning knowledge summary for user {current_user.email}: {response_data.model_dump()}")
        return response_data

    except Exception as e:
        logger.error(f"General error fetching knowledge summary for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge base summary."
        )

@router.post("/snippet")
async def ingest_snippet(
    snippet: SnippetRequest,
    current_user: User = Depends(get_current_user),
    vector_db_client: MilvusClient = Depends(get_milvus_client)
):
    """
    Ingest a freeform text snippet into the user's RAG knowledge base.
    Body JSON should be {"content": "...", "metadata": {...}}.
    """
    # Validate and parse request
    text = snippet.content
    metadata = snippet.metadata or {}
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing 'content' in request body.")
    # Normalize tag to lowercase to ensure consistent retrieval
    if 'tag' in metadata and isinstance(metadata['tag'], str):
        metadata['tag'] = metadata['tag'].strip().lower()
    # Mark this point as a snippet source for later retrieval filtering
    metadata['source'] = 'snippet'
    # Create embedding for the full snippet
    embedding = await create_embedding(text)
    # Determine user-specific collection
    sanitized = current_user.email.replace('@', '_').replace('.', '_')
    collection = f"{sanitized}_knowledge_base"
    # Create a single Qdrant point for the entire snippet
    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=embedding,
        payload={"content": text, **metadata}
    )
    # Upsert into Qdrant
    vector_db_client.upsert(collection_name=collection, points=[point], wait=True)
    return {"status": "success", "id": point.id, "collection": collection} 

@router.post("/add_text", response_model=AddTextResponse, status_code=status.HTTP_201_CREATED)
async def add_text_to_knowledge(
    request_data: AddTextRequest,
    current_user: User = Depends(get_current_user),
    vector_db_client: MilvusClient = Depends(get_milvus_client) # Updated dependency
):
    # Implementation for adding text and embedding to Milvus goes here
    logger.info(f"Received request to add text from user {current_user.email}")
    
    # Determine target collection (use request or default based on user/logic)
    target_collection = request_data.collection_name or f"{current_user.email.replace('@','_').replace('.','_')}_knowledge_base"
    
    try:
        # 1. Generate embedding for the text
        embedding = await create_embedding(request_data.text)
        logger.debug(f"Generated embedding for text snippet.")

        # 2. Prepare data for Milvus
        point_id = str(uuid.uuid4())
        payload = request_data.metadata or {}
        # Add the raw text itself to the payload if desired
        payload["text"] = request_data.text 
        # Ensure basic user/source info is present
        payload["owner"] = current_user.email
        payload["source"] = "manual_text_input"
        payload["added_at"] = datetime.now(timezone.utc).isoformat()

        milvus_data = {
            "id": point_id,
            "vector": embedding,
            "payload": payload
        }
        logger.debug(f"Prepared data for Milvus insertion: ID={point_id}")

        # 3. Ensure collection exists (optional, depending on setup)
        # ensure_collection_exists(vector_db_client, target_collection, settings.EMBEDDING_DIMENSION)

        # 4. Insert into Milvus
        # Note: MilvusClient insert expects a list of dicts or a list of lists/tuples
        # Adjust based on the specific schema you'll define for the collection
        # Assuming schema matches the dict structure for now
        vector_db_client.insert(collection_name=target_collection, data=[milvus_data])
        logger.info(f"Successfully inserted text snippet with ID {point_id} into collection '{target_collection}'")
        
        return AddTextResponse(id=point_id, status="success")

    except Exception as e:
        logger.error(f"Failed to add text snippet to collection '{target_collection}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add text to knowledge base: {str(e)}"
        ) 