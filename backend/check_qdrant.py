import sys
import os
import asyncio
import logging
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Explicitly load the .env file from the backend directory
env_path = os.path.join(os.path.dirname(__file__), '.env')
loaded = load_dotenv(dotenv_path=env_path)
print(f"Attempted to load .env from: {env_path}")
print(f".env file loaded: {loaded}")

# Get values directly from os.getenv AFTER loading .env
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_connection():
    print("--- Qdrant Connection Check (Direct Env Load) --- ")
    print(f"Attempting to connect to Qdrant URL: {qdrant_url}")
    print(f"Using API Key: {'Yes' if qdrant_api_key else 'No'}")

    if not qdrant_url:
        print("ERROR: QDRANT_URL not found after loading .env.")
        return

    client: QdrantClient = None
    try:
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key
        )
        # Try listing collections as a basic check
        print("Attempting to list collections...")
        collections = client.get_collections()
        print("\nSUCCESS: Connection established and collections listed!")
        print("Collections:")
        print(collections)

    except Exception as e:
        print(f"\nERROR: Failed to connect or perform operation on Qdrant.")
        print(f"Error details: {e}")
        print("\nPlease check:")
        print("1. Qdrant instance is running and accessible at the URL.")
        print("2. QDRANT_URL in .env is correct.")
        print("3. QDRANT_API_KEY in .env is correct (if required by your Qdrant instance).")
        print("4. Network connectivity (firewalls, proxies).")

if __name__ == "__main__":
    asyncio.run(check_connection()) 