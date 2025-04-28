import os
import sys
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer # Import SentenceTransformer

# Ensure the script can find the backend modules
script_dir = os.path.dirname(os.path.abspath(__file__)) # Use absolute path of the script
backend_root = os.path.abspath(os.path.join(script_dir, 'backend')) # Go up one level and into backend
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Now try importing backend modules
try:
    from app.db.milvus_client import get_milvus_client
    from app.config import settings
    from pymilvus import utility, Collection, FieldSchema, CollectionSchema, DataType
    # Removed embedder import: from app.services.embedder import get_embedding_model
except ImportError as e:
    print(f"Error importing backend modules: {e}. Is the backend directory accessible?")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from the backend/.env file
dotenv_path = os.path.join(backend_root, '.env')
load_dotenv(dotenv_path=dotenv_path)
logger.info(f"Starting Milvus search script... Loaded .env from: {dotenv_path}")

# --- Configuration ---
COLLECTION_NAME = "kianwoon_wong_int_beyondsoft_com_knowledge_base_bm" # Replace with your actual collection name if different
SEARCH_TERM = "document" # Use a generic term to try and retrieve all chunks
SEARCH_LIMIT = 10 # Increase limit to capture all reported points

# Initialize embedding model directly
try:
    logger.info(f"Loading SentenceTransformer model: {settings.DENSE_EMBEDDING_MODEL}")
    embedder = SentenceTransformer(settings.DENSE_EMBEDDING_MODEL)
    logger.info("SentenceTransformer model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load SentenceTransformer model: {e}", exc_info=True)
    sys.exit(1)

# --- Milvus Interaction ---
try:
    client = get_milvus_client()
    if not client:
        logger.error("Failed to get Milvus client. Exiting.")
        sys.exit(1)

    logger.info(f"Successfully obtained Milvus client object. Searching collection '{COLLECTION_NAME}'...")

    # Check if collection exists using the client object
    if not client.has_collection(COLLECTION_NAME):
        logger.error(f"Collection '{COLLECTION_NAME}' does not exist.")
        sys.exit(1)

    # Load collection using the client object
    logger.info(f"Loading collection '{COLLECTION_NAME}'...")
    client.load_collection(COLLECTION_NAME)
    logger.info(f"Collection '{COLLECTION_NAME}' loaded.")

    # Create embedding for the search term using the loaded model
    logger.info(f"Generating embedding for search term: '{SEARCH_TERM}'")
    search_vector_raw = embedder.encode(SEARCH_TERM)

    # --- Vector extraction logic (handle potential list wrapping) ---
    search_vector = None
    # SentenceTransformer encode usually returns a numpy array, convert to list
    if hasattr(search_vector_raw, 'tolist'):
        search_vector = search_vector_raw.tolist()
        logger.debug("Converted numpy embedding to list.")
    elif isinstance(search_vector_raw, list):
         # Handle cases where it might already be a list (less common for encode)
        if len(search_vector_raw) == 1 and isinstance(search_vector_raw[0], list) and isinstance(search_vector_raw[0][0], float):
            search_vector = search_vector_raw[0] # Handle [['vector']]
            logger.debug("Extracted vector from nested list format.")
        elif len(search_vector_raw) > 0 and isinstance(search_vector_raw[0], float):
            search_vector = search_vector_raw # Handle ['vector']
            logger.debug("Using vector directly from list format.")

    if search_vector is None:
        logger.error(f"Could not extract a valid float vector from embedding result. Type: {type(search_vector_raw)}, Value: {search_vector_raw}")
        sys.exit(1)
    # --- End vector extraction logic ---

    logger.info(f"Embedding generated successfully. Vector dimension: {len(search_vector)}")

    # Define search parameters for MilvusClient.search
    # These are now passed directly as keyword arguments below
    # search_params = {
    #     "metric_type": "COSINE", # Or L2, IP
    #     "params": {"ef": 128}, # Adjust search params as needed
    # }

    # Perform the search using the client object
    logger.info(f"Performing search in collection '{COLLECTION_NAME}'...")
    try:
        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[search_vector], # List of query vectors
            anns_field="dense", # Field name of the vector
            # Pass metric_type and params directly
            metric_type="COSINE", # Or L2, IP
            params={"ef": 128}, # Search parameters like ef (for HNSW), nprobe (for IVF)
            limit=SEARCH_LIMIT,
            output_fields=["id", "content", "metadata", "job_id"] # Fields to return
        )
    except Exception as search_error:
        logger.error(f"Failed to search collection: {COLLECTION_NAME}", exc_info=True)
        raise search_error # Re-raise after logging

    logger.info(f"Search completed. Found {len(results[0]) if results else 0} results.")
    print("\n--- Milvus Search Results ---")
    if results and len(results[0]) > 0:
        # MilvusClient returns a list of lists of hits (one list per query vector)
        # Each hit is a dictionary
        for i, hit in enumerate(results[0]):
            print(f"Result {i+1}:")
            print(f"  ID: {hit.get('id', 'N/A')}")
            print(f"  Distance: {hit.get('distance', 'N/A'):.4f}")
            # Access entity data directly from the hit dictionary
            print(f"  Content (start): {hit.get('entity', {}).get('content', 'N/A')[:150]}...")
            print(f"  Metadata: {hit.get('entity', {}).get('metadata', 'N/A')}")
            print(f"  Job ID: {hit.get('entity', {}).get('job_id', 'N/A')}")
            print("-" * 20)
    else:
        print("No results found.")

    print("--- End of Results ---")

except Exception as e:
    logger.error(f"An error occurred: {e}", exc_info=True)
finally:
    # MilvusClient manages its own connections, no explicit close usually needed here
    # unless specific cleanup is required.
    logger.info("Script finished.") 