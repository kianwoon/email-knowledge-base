import logging
from pymilvus import connections, utility, Collection, MilvusClient
# Import necessary schema components
from pymilvus import CollectionSchema, FieldSchema, DataType
from app.config import settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)

_milvus_client = None

def get_milvus_client() -> MilvusClient:
    """
    Initializes and returns a Milvus client using settings from the environment.
    Uses a singleton pattern to reuse the client instance.
    """
    global _milvus_client
    if _milvus_client is None:
        logger.info(f"Initializing Milvus client for URI: {settings.MILVUS_URI}")
        try:
            # MilvusClient uses URI and token directly
            _milvus_client = MilvusClient(
                uri=settings.MILVUS_URI,
                token=settings.MILVUS_TOKEN,
                # timeout=60.0 # Optional: Specify timeout if needed
            )
            # Check if the connection is successful (optional, depends on MilvusClient behavior)
            # Example: Check if a basic operation like list_collections works
            _milvus_client.list_collections() # Verifies basic connectivity
            logger.info("Milvus client connection verified.")

            # Ensure the default collection exists
            default_dim = settings.DENSE_EMBEDDING_DIMENSION
            ensure_collection_exists(
                client=_milvus_client,
                collection_name=settings.MILVUS_DEFAULT_COLLECTION,
                dim=default_dim
            )
            logger.info(f"Milvus client initialized and collection '{settings.MILVUS_DEFAULT_COLLECTION}' ensured.")
        except Exception as e:
            logger.error(f"Failed to initialize Milvus client or ensure collection: {e}", exc_info=True)
            _milvus_client = None # Reset on failure
            raise HTTPException(status_code=503, detail=f"Could not connect to Milvus: {e}")
    return _milvus_client

def ensure_collection_exists(client: MilvusClient, collection_name: str, dim: int):
    """
    Checks if the Milvus collection exists and creates it if not using a predefined schema.
    """
    logger.info(f"Ensuring Milvus collection '{collection_name}' exists with dimension {dim}.")
    try:
        if client.has_collection(collection_name=collection_name):
            logger.warning(f"Milvus collection '{collection_name}' already exists. Dropping and recreating for schema consistency during debugging.")
            client.drop_collection(collection_name=collection_name)
            logger.info(f"Milvus collection '{collection_name}' dropped.")

        logger.info(f"Creating Milvus collection '{collection_name}' with dimension {dim}.")
        
        # Define the schema based on ACTUAL reported schema
        # Primary Key Field
        id_field = FieldSchema(
            name="id", # ACTUAL NAME
            dtype=DataType.VARCHAR, 
            is_primary=True, 
            auto_id=False, # We provide our own UUIDs
            max_length=100 # ACTUAL LENGTH
        )
        # Vector Field
        dense_vector_field = FieldSchema(
            name="dense", # ACTUAL NAME
            dtype=DataType.FLOAT_VECTOR, 
            dim=dim # Dimension seems correct (e.g., 1024)
        )
        # Other ACTUAL top-level fields from schema description
        # sparse_vector_field = FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR) # Temporarily commented out
        job_id_field = FieldSchema(name="job_id", dtype=DataType.VARCHAR, max_length=100) # ACTUAL LENGTH
        content_field = FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535) # ACTUAL LENGTH
        chunk_index_field = FieldSchema(name="chunk_index", dtype=DataType.INT64)
        sensitivity_field = FieldSchema(name="sensitivity", dtype=DataType.VARCHAR, max_length=50) # ACTUAL LENGTH
        
        # Using JSON for tags and other metadata for broader compatibility for now
        metadata_field = FieldSchema(name="metadata", dtype=DataType.JSON) # ACTUAL NAME
        # NOTE: owner, source, type, email_id, subject, date, status, folder, etc. are NOT top-level fields
        # They should reside within the 'metadata' JSON field if used during ingestion.

        schema = CollectionSchema(
            # Use the ACTUAL field names and structure
            fields=[
                id_field, 
                dense_vector_field, 
                # sparse_vector_field, # Temporarily commented out
                job_id_field,
                content_field,
                chunk_index_field,
                metadata_field,
                sensitivity_field 
            ],
            description=f"Collection for storing knowledge data for {collection_name}",
            enable_dynamic_field=True # ACTUAL VALUE is True
        )
        
        # Define index parameters (example using IVF_FLAT, adjust as needed)
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="dense", # ACTUAL vector field name
            index_type="IVF_FLAT", # Example index type
            metric_type="COSINE", # Or L2, IP based on embedding type
            params={"nlist": 128} # Example param
        )
        
        # Add index for sparse vector if needed (example, adjust type)
        # if 'sparse_vector_field' in locals() and sparse_vector_field is not None: # Only if field exists
        #     index_params.add_index(
        #         field_name="sparse",
        #         index_type="SPARSE_INVERTED_INDEX", # Or other sparse index type
        #         metric_type="IP"
        #     )

        # Create the collection
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            consistency_level="Bounded" # Example consistency level, adjust as needed
        )
        logger.info(f"Milvus collection '{collection_name}' created successfully.")

        # Create the index after collection creation
        client.create_index(collection_name=collection_name, index_params=index_params)
        logger.info(f"Index created for vector field in '{collection_name}'.")
        
        # Load the collection into memory to ensure it's queryable immediately
        client.load_collection(collection_name=collection_name)
        logger.info(f"Collection '{collection_name}' loaded into memory.")

    except Exception as e:
        logger.error(f"Error checking or creating Milvus collection '{collection_name}': {e}", exc_info=True)
        # Avoid raising HTTPException here directly, let the calling function handle it
        # Raise the original exception to signal failure
        raise e

# Example usage (can be removed or adapted)
if __name__ == "__main__":
    try:
        client = get_milvus_client()
        print("Successfully connected to Milvus.")
        # Example: Ensure a default collection exists (using default dimension from settings)
        # Note: settings.EMBEDDING_DIMENSION might still point to the old Qdrant config if not updated everywhere.
        # Consider adding a MILVUS_DEFAULT_DIMENSION to settings or using a specific value here.
        default_dim = settings.DENSE_EMBEDDING_DIMENSION # Using DENSE_EMBEDDING_DIMENSION as a likely candidate
        ensure_collection_exists(client, settings.MILVUS_DEFAULT_COLLECTION, default_dim)
        print(f"Checked/ensured collection '{settings.MILVUS_DEFAULT_COLLECTION}' with dimension {default_dim}")
    except HTTPException as e:
        print(f"HTTPException connecting or ensuring collection in Milvus: {e.detail}")
    except Exception as e:
        print(f"Failed during Milvus client example usage: {e}")
