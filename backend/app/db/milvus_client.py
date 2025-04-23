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
            _milvus_client.list_collections()
            logger.info("Milvus client initialized and connection verified.")
        except Exception as e:
            logger.error(f"Failed to initialize Milvus client: {e}", exc_info=True)
            _milvus_client = None # Reset on failure
            raise HTTPException(status_code=503, detail=f"Could not connect to Milvus: {e}")
    return _milvus_client

def ensure_collection_exists(client: MilvusClient, collection_name: str, dim: int):
    """
    Checks if the Milvus collection exists and creates it if not using a predefined schema.
    """
    logger.info(f"Ensuring Milvus collection '{collection_name}' exists with dimension {dim}.")
    try:
        exists = client.has_collection(collection_name=collection_name)
        if exists:
            logger.info(f"Milvus collection '{collection_name}' already exists.")
            # Optional: Add schema compatibility checks here if needed in the future.
            # e.g., compare client.describe_collection(collection_name).schema with expected schema.
            return
        else:
            logger.info(f"Milvus collection '{collection_name}' does not exist. Creating...")
            
            # Define the schema
            # Primary Key Field
            pk_field = FieldSchema(
                name="pk", 
                dtype=DataType.VARCHAR, 
                is_primary=True, 
                auto_id=False, # We provide our own UUIDs
                max_length=36 # Length of UUID string
            )
            # Vector Field
            vector_field = FieldSchema(
                name="vector", 
                dtype=DataType.FLOAT_VECTOR, 
                dim=dim
            )
            # Metadata Fields (adjust max_length as needed)
            owner_field = FieldSchema(name="owner", dtype=DataType.VARCHAR, max_length=255)
            source_field = FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=50)
            type_field = FieldSchema(name="type", dtype=DataType.VARCHAR, max_length=50)
            email_id_field = FieldSchema(name="email_id", dtype=DataType.VARCHAR, max_length=255, default_value="") # Allow null/empty
            job_id_field = FieldSchema(name="job_id", dtype=DataType.VARCHAR, max_length=36, default_value="")
            subject_field = FieldSchema(name="subject", dtype=DataType.VARCHAR, max_length=1024, default_value="")
            date_field = FieldSchema(name="date", dtype=DataType.VARCHAR, max_length=50, default_value="")
            status_field = FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=50, default_value="")
            folder_field = FieldSchema(name="folder", dtype=DataType.VARCHAR, max_length=255, default_value="")
            # tags_field = FieldSchema(name="tags", dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_capacity=100, max_length=100) # Requires Milvus 2.3+
            # Using JSON for tags and other metadata for broader compatibility for now
            metadata_json_field = FieldSchema(name="metadata_json", dtype=DataType.JSON)

            schema = CollectionSchema(
                fields=[pk_field, vector_field, owner_field, source_field, type_field, email_id_field, job_id_field, subject_field, date_field, status_field, folder_field, metadata_json_field],
                description=f"Collection for storing knowledge data for {collection_name}",
                enable_dynamic_field=False # Explicitly disable dynamic fields unless needed
            )
            
            # Define index parameters (example using IVF_FLAT, adjust as needed)
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="IVF_FLAT", # Example index type
                metric_type="COSINE", # Or L2, IP based on embedding type
                params={"nlist": 128} # Example param
            )
            
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
            
            # Load the collection into memory (optional, depends on use case)
            # client.load_collection(collection_name=collection_name)
            # logger.info(f"Collection '{collection_name}' loaded into memory.")

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