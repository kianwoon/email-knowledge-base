# MilvusClient uses URI and token directly
_milvus_client = MilvusClient(
    uri=settings.MILVUS_URI,
    token=settings.MILVUS_TOKEN,
    timeout=60.0 # Optional: Specify timeout if needed
)
# Check if the connection is successful (optional, depends on MilvusClient behavior)
# Example: Check if a basic operation like list_collections works 