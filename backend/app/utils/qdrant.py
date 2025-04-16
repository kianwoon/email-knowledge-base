from qdrant_client import QdrantClient, models
from app.config import settings
import logging
from app.db.qdrant_client import ensure_collection_exists, get_qdrant_client

logger = logging.getLogger(__name__)

def upsert_to_qdrant(points, collection_name=None):
    """
    Upsert a list of points (each with id, vector, payload) into the specified Qdrant collection.
    If collection_name is not provided, uses the default from settings.
    Ensures the collection exists before upserting.
    """
    collection = collection_name or getattr(settings, 'QDRANT_DEFAULT_COLLECTION', getattr(settings, 'QDRANT_COLLECTION_NAME', 'custom_knowledge'))
    url = getattr(settings, 'QDRANT_URL', 'http://localhost:6333')
    api_key = getattr(settings, 'QDRANT_API_KEY', None)
    client = QdrantClient(url=url, api_key=api_key)
    logger.info(f"Ensuring Qdrant collection '{collection}' exists at {url}")
    ensure_collection_exists(client, collection)
    logger.info(f"Upserting {len(points)} points to Qdrant collection '{collection}' at {url}")
    try:
        # Convert points to models.PointStruct if needed
        qdrant_points = []
        for p in points:
            qdrant_points.append(models.PointStruct(
                id=p['id'],
                vector=p['vector'],
                payload=p['payload']
            ))
        client.upsert(
            collection_name=collection,
            points=qdrant_points
        )
        logger.info(f"Upserted {len(points)} points to Qdrant collection '{collection}'")
    except Exception as e:
        logger.error(f"Failed to upsert points to Qdrant: {e}", exc_info=True)
        raise
