from typing import List, Tuple, Dict
import base64
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sqlalchemy.orm import Session
from app.db.crud.azure_blob_sync_item import crud_azure_blob_sync_item
from app.models.azure_blob_sync_item import AzureBlobSyncItem
from app.services.azure_blob_service import AzureBlobService
from app.core.config import settings
from app.core.logger import logger
from app.db.session import SessionLocal
from app.crud import crud_azure_blob, user_crud
from celery import Task
from app.celery_app import celery_app
import asyncio

async def _process_items_for_connection(
    azure_service: AzureBlobService,
    items: List[AzureBlobSyncItem],
    db: Session,
    task_id: str,
    zero_vector: List[float]
) -> Tuple[List[qdrant_models.PointStruct], int, int]:
    points_for_connection = []
    processed_count = 0
    failed_count = 0
    points_for_prefix = []
    point_to_add = None

    for item in items:
        try:
            point_to_add = None
            points_for_prefix = []

            if item.item_type == 'blob':
                blob_content_bytes = await azure_service.download_blob_content(item.container_name, item.item_path)
                if blob_content_bytes:
                    content_b64 = base64.b64encode(blob_content_bytes).decode('utf-8')
                    point_id = str(uuid.uuid4())
                    metadata = {
                        "source": "azure_blob", "document_id": item.item_path, "connection_id": str(item.connection_id),
                        "container": item.container_name, "path": item.item_path, "filename": item.item_path.split('/')[-1],
                        "analysis_status": "pending", "content_b64": content_b64,
                    }
                    point_to_add = qdrant_models.PointStruct(id=point_id, vector=zero_vector, payload=metadata)
                else:
                     logger.warning(f"Task {task_id}: No content downloaded for blob {item.item_path}. Skipping.")
            elif item.item_type == 'prefix':
                blobs_under_prefix = await azure_service.list_blobs(item.container_name, item.item_path)
                for blob_info in blobs_under_prefix:
                    if not blob_info.get('isDirectory'):
                        blob_path = blob_info.get('path')
                        blob_name = blob_info.get('name')
                        if not blob_path or not blob_name:
                            continue
                        blob_content_bytes = await azure_service.download_blob_content(item.container_name, blob_path)
                        if blob_content_bytes:
                            content_b64 = base64.b64encode(blob_content_bytes).decode('utf-8')
                            point_id = str(uuid.uuid4())
                            metadata = {
                                "source": "azure_blob", "document_id": blob_path, "connection_id": str(item.connection_id),
                                "container": item.container_name, "path": blob_path, "filename": blob_name,
                                "analysis_status": "pending", "content_b64": content_b64,
                            }
                            points_for_prefix.append(qdrant_models.PointStruct(id=point_id, vector=zero_vector, payload=metadata))
                        else:
                            logger.warning(f"Task {task_id}: No content downloaded for blob {blob_path} under prefix. Skipping.")
                if points_for_prefix:
                     points_for_connection.extend(points_for_prefix)
                     logger.info(f"Task {task_id}: Generated {len(points_for_prefix)} points for prefix item {item.id} ('{item.item_path}')")
                else:
                     logger.info(f"Task {task_id}: No processable blobs found under prefix item {item.id} ('{item.item_path}').")

            if point_to_add:
                points_for_connection.append(point_to_add)
                logger.info(f"Task {task_id}: Generated 1 point for blob item {item.id} ('{item.item_path}')")

            if point_to_add or points_for_prefix:
                crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='completed')
                processed_count += 1
                logger.info(f"Task {task_id}: Completed processing item {item.id}")
            else:
                logger.warning(f"Task {task_id}: No points generated for item {item.id}. Marking as failed.")
                crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
                failed_count += 1

        except Exception as item_err:
            logger.error(f"Task {task_id}: Error processing item {item.id} ({item.item_path}): {item_err}", exc_info=True)
            failed_count += 1
            try:
                crud_azure_blob_sync_item.update_sync_item_status(db, db_item=item, status='failed')
            except Exception as status_err:
                logger.error(f"Task {task_id}: Additionally failed to mark item {item.id} as failed: {status_err}")
            continue

    return points_for_connection, processed_count, failed_count


# Renamed async function containing the core logic
async def _execute_azure_ingestion_logic(user_id_str: str, task_id: str):
    logger.info(f"Task {task_id}: Starting async Azure Blob ingestion logic for user ID {user_id_str}.")
    db: Session = SessionLocal()
    cumulative_processed = 0
    cumulative_failed = 0
    all_points_to_upsert = []
    final_status = "UNKNOWN"
    final_message = "Task did not complete fully."
    pending_items = None
    user = None # Initialize user to None

    try:
        # 1. User Lookup and Qdrant Client Setup
        user_id = uuid.UUID(user_id_str) # Convert string ID to UUID
        user = user_crud.get_user(db, user_id=user_id) # Corrected function call
        if not user:
            raise Exception(f"User with ID {user_id_str} not found.")
        
        qdrant_client = QdrantClient(settings.QDRANT_URL, port=settings.QDRANT_PORT, api_key=settings.QDRANT_API_KEY)
        collection_name = f"user_{user_id_str}_documents"

        # 2. Get Pending Items
        # Use user.id (which is a UUID) directly
        pending_items = crud_azure_blob_sync_item.get_sync_items(db, user_id=user.id, connection_id=None, status='pending') 
        if not pending_items:
            logger.info(f"Task {task_id}: No pending Azure Blob sync items found for user {user_id_str}.")
            return {"status": "COMPLETE", "message": "No pending items.", "processed": 0, "failed": 0}
        
        logger.info(f"Task {task_id}: Found {len(pending_items)} pending items.")

        # Group items by connection_id
        items_by_connection = {}
        for item in pending_items:
            if item.connection_id not in items_by_connection:
                items_by_connection[item.connection_id] = []
            items_by_connection[item.connection_id].append(item)

        zero_vector = [0.0] * settings.EMBEDDING_DIM

        # 3. Process Items per Connection
        for conn_id, items in items_by_connection.items():
            logger.info(f"Task {task_id}: Processing connection {conn_id}...")
            connection = crud_azure_blob.get_connection_with_decrypted_credentials(
                db, connection_id=conn_id, user_id=user.id
            )
            
            if not connection:
                logger.error(f"Task {task_id}: Connection {conn_id} error. Skipping.")
                cumulative_failed += len(items)
                # Mark failed
                for item in items:
                    try:
                        crud_azure_blob_sync_item.update_sync_item_status(
                            db, db_item=item, status='failed'
                        )
                    except Exception as status_err:
                        logger.error(
                            f"Task {task_id}: Failed marking item {item.id} as failed: {status_err}"
                        )
                continue

            try:
                async with AzureBlobService(connection_string=connection.credentials) as azure_service:
                    points, processed, failed = await _process_items_for_connection(
                        azure_service, items, db, task_id, zero_vector
                    )
                    all_points_to_upsert.extend(points)
                    cumulative_processed += processed
                    cumulative_failed += failed
            except Exception as conn_err:
                logger.error(
                    f"Task {task_id}: Error processing connection {conn_id}: {conn_err}",
                    exc_info=True
                )
                cumulative_failed += len(items)  # Assume all failed
                # Mark failed
                for item in items:
                    try:
                        if item.status in ('pending', 'processing'):
                            crud_azure_blob_sync_item.update_sync_item_status(
                                db, db_item=item, status='failed'
                            )
                    except Exception as status_err:
                        logger.error(
                            f"Task {task_id}: Failed marking item {item.id} as failed: {status_err}"
                        )
                continue

        # 4. Upsert points to Qdrant
        if all_points_to_upsert:
            logger.info(
                f"Task {task_id}: Upserting {len(all_points_to_upsert)} points to Qdrant collection '{collection_name}'."
            )
            try:
                collection_exists = False
                try:
                    qdrant_client.get_collection(collection_name=collection_name)
                    collection_exists = True
                except Exception as e:
                    if "not found" in str(e).lower() or "status_code=404" in str(e).lower():
                        collection_exists = False
                    else:
                        raise e
                
                if not collection_exists:
                    qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=qdrant_models.VectorParams(
                            size=settings.EMBEDDING_DIM,
                            distance=qdrant_models.Distance.COSINE
                        )
                    )
                logger.info(f"Task {task_id}: Ensured Qdrant collection '{collection_name}' exists.")

                qdrant_client.upsert(
                    collection_name=collection_name,
                    points=all_points_to_upsert,
                    wait=True
                )
                logger.info(f"Task {task_id}: Successfully upserted points.")
            except Exception as q_err:
                logger.error(f"Task {task_id}: Qdrant upsert failed: {q_err}", exc_info=True)
                final_status = "FAILED"
                final_message = f"Qdrant upsert failed: {q_err}"
        else:
            logger.info(f"Task {task_id}: No points generated for Qdrant upsert.")

        # 5. Determine final status and message
        total_items = len(pending_items) if pending_items else 0
        if cumulative_failed == 0 and cumulative_processed == total_items:
            final_status = "COMPLETE"
            final_message = "All items processed successfully."
        elif cumulative_processed > 0:
            final_status = "PARTIAL_COMPLETE"
            final_message = f"Processed {cumulative_processed}/{total_items} items, {cumulative_failed} failed."
        elif cumulative_failed == total_items and total_items > 0:
            final_status = "FAILED"
            final_message = "All items failed processing."
        elif total_items == 0:  # Already handled earlier, but as a safeguard
            final_status = "COMPLETE"
            final_message = "No items needed processing."
        else:  # Catch-all for unexpected count scenarios
            final_status = "FAILED"
            final_message = f"Task finished with unclear state. Processed: {cumulative_processed}, Failed: {cumulative_failed}, Total: {total_items}"

        logger.info(f"Task {task_id}: Final status: {final_status}, Message: {final_message}")
        return {
            "status": final_status,
            "message": final_message,
            "processed": cumulative_processed,
            "failed": cumulative_failed
        }

    except Exception as e:
        logger.error(f"Task {task_id}: Unhandled error in async logic: {e}", exc_info=True)
        num_pending = len(pending_items) if pending_items else 0
        failed_in_exception = num_pending - cumulative_processed
        return {
            "status": "FAILED",
            "message": str(e),
            "processed": cumulative_processed,
            "failed": cumulative_failed + failed_in_exception
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.azure.process_ingestion", max_retries=3, default_retry_delay=60)
def process_azure_ingestion_task(self: Task, user_id_str: str):
    logger.info(f"Task {self.request.id}: Received Azure Blob ingestion request for user ID {user_id_str}. Running async logic...")
    self.update_state(state='STARTED', meta={'progress': 0, 'status': 'Initializing...'})

    try:
        result = asyncio.run(_execute_azure_ingestion_logic(user_id_str=user_id_str, task_id=self.request.id))

        final_meta = {
            'progress': 100,
            'status': str(result.get('status', 'UNKNOWN')),
            'message': str(result.get('message', 'Async execution finished.')),
            'processed': int(result.get('processed', 0)),
            'failed': int(result.get('failed', 0))
        }
        final_celery_state = 'SUCCESS' if result.get('status') in ['COMPLETE', 'PARTIAL_COMPLETE'] else 'FAILURE'

        logger.info(f"Task {self.request.id}: Async logic completed. Final state: {final_celery_state}, Meta: {final_meta}")
        self.update_state(state=final_celery_state, meta=final_meta)
        return final_meta

    except Exception as e:
        error_message = f"Error in synchronous wrapper or during async execution: {e}"
        logger.error(f"Task {self.request.id}: {error_message}", exc_info=True)
        raise