import logging
from pymilvus import MilvusClient, utility

# Import settings to get connection details
# Assuming settings are accessible via app.config
# Adjust the import path if necessary based on your project structure
try:
    from app.config import settings
except ImportError:
    print("Error: Could not import settings from app.config. Please ensure this script is run")
    print("from the root directory or adjust the import path.")
    exit(1)

# Configure logging (optional, but helpful)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
# !!! Replace with the actual collection name you want to check !!!
# Extracting from logs, needs confirmation if the user part changes
USER_EMAIL_SANITIZED = "kianwoon_wong_int_beyondsoft_com" 
COLLECTION_NAME = f"{USER_EMAIL_SANITIZED}_knowledge_base_bm" 
# --- End Configuration ---


def check_collection_schema(collection_name: str):
    """Connects to Milvus and prints the schema details for the given collection."""
    
    if not settings.MILVUS_URI or not settings.MILVUS_TOKEN:
        logger.error("Milvus URI or Token is not configured in settings. Please check your .env file.")
        return

    logger.info(f"Attempting to connect to Milvus at: {settings.MILVUS_URI}")
    
    try:
        # Initialize Milvus Client
        client = MilvusClient(
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN
        )
        logger.info("Successfully initialized Milvus client.")

        # Check if collection exists
        if not utility.has_collection(collection_name, using='default', client=client):
             logger.error(f"Collection '{collection_name}' does not exist.")
             client.close()
             return

        logger.info(f"Fetching schema for collection: {collection_name}")
        
        # Get collection description
        collection_info = client.describe_collection(collection_name=collection_name)
        
        logger.info("--- Collection Schema --- ")
        print(collection_info) # Print the full schema details
        
        # Specifically look for vector field dimensions
        if collection_info and hasattr(collection_info, 'fields'):
             print("\n--- Vector Field Dimensions --- ")
             found_vector = False
             for field in collection_info.fields:
                 if hasattr(field, 'params') and 'dim' in field.params:
                     found_vector = True
                     print(f"Field Name: '{field.name}', Dimension: {field.params['dim']}")
             if not found_vector:
                 print("No vector fields with explicit dimension found in schema.")
        else:
            logger.warning("Could not extract detailed field information from schema description.")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        if 'client' in locals() and client:
            try:
                client.close()
                logger.info("Milvus client connection closed.")
            except Exception as ce:
                logger.error(f"Error closing Milvus connection: {ce}")

if __name__ == "__main__":
    if COLLECTION_NAME == "{USER_EMAIL_SANITIZED}_knowledge_base_bm" and USER_EMAIL_SANITIZED == "your_sanitized_email_here":
         print("Error: Please update the USER_EMAIL_SANITIZED variable in the script with the correct value.")
    else:
        check_collection_schema(COLLECTION_NAME) 