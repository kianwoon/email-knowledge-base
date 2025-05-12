# backend/app/tasks/export_tasks.py
import logging
import asyncio
from typing import Dict, Any, Optional, List
import io
import csv
import datetime
from datetime import timezone

from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.config import settings

# Import models and CRUD
from app.db.models.export_job import ExportJob, ExportJobStatus
from app.models.token_models import TokenDB
from app.crud import crud_export_job, token_crud

# Import services needed for data fetching/storage
from app.services.duckdb import query_iceberg_emails_duckdb
from app.services import s3 as r2_service
# Import counters for auditing from the new metrics module
from app.metrics import ATTACHMENT_REDACTIONS # Add other counters if needed

logger = logging.getLogger(__name__)


class ExportProcessingTask(Task):
    """Base class for export tasks to manage DB sessions etc."""
    _db: Optional[Session] = None
    _r2_client: Optional[Any] = None

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Close DB session after task completion."""
        if self._db:
            self._db.close()
            logger.debug(f"Task {task_id}: Database session closed.")
            self._db = None
        # Note: R2 client might not need explicit closing depending on implementation

    @property
    def db(self) -> Session:
        """Provides a DB session per task instance."""
        if self._db is None:
            self._db = SessionLocal()
            logger.debug(f"Task {self.request.id}: Database session created.")
        return self._db

    @property
    def r2_client(self) -> Any:
        """Provides an R2 client per task instance."""
        if self._r2_client is None:
            # Assuming get_r2_client doesn't require async context here
            # If it does, this needs adjustment (e.g., initialize in task run)
            self._r2_client = r2_service.get_r2_client()
            logger.debug(f"Task {self.request.id}: R2 client initialized.")
        return self._r2_client

# Placeholder for the actual task
@celery_app.task(bind=True, base=ExportProcessingTask, name='tasks.export.export_data', time_limit=1800, soft_time_limit=1700)
async def export_data_task(self: ExportProcessingTask, job_id: int):
    logger.info(f"Task {self.request.id}: Starting export for Job ID {job_id}.")
    self.update_state(state='STARTED', meta={'job_id': job_id, 'status': 'Initializing...'})

    job: Optional[ExportJob] = None
    token: Optional[TokenDB] = None
    final_status = ExportJobStatus.FAILED
    error_message = "Unknown error"
    result_location = None
    celery_state = 'FAILURE'
    # Counters for auditing
    rows_processed = 0
    rows_exported = 0
    attachments_redacted_count = 0
    vectors_redacted_count = 0

    try:
        db = self.db
        r2 = self.r2_client
        job = crud_export_job.get_export_job(db=db, job_id=job_id)
        if not job:
            raise ValueError(f"ExportJob {job_id} not found.")

        if job.status not in [ExportJobStatus.PENDING, ExportJobStatus.FAILED]:
            logger.warning(f"Task {self.request.id}: Job {job_id} has status '{job.status}', skipping.")
            self.update_state(state='SUCCESS', meta={'job_id': job_id, 'status': 'Skipped (already processed)'})
            return {'status': 'skipped', 'reason': f'Job already in status {job.status}'}

        # Update job status to PROCESSING
        crud_export_job.update_job_status(db=db, job_id=job_id, status=ExportJobStatus.PROCESSING)
        self.update_state(state='PROGRESS', meta={'job_id': job_id, 'status': 'Processing...'})

        # 1. Fetch Token
        token = token_crud.get_token_by_id(db=db, token_id=job.token_id)
        if not token:
            raise ValueError(f"Token ID {job.token_id} associated with Job {job_id} not found.")
        logger.info(f"Task {self.request.id}: Using token {token.id} ('{token.name}') for export rules.")

        # 2. Parse export_params (assuming source=ICEBERG_EMAIL_FACTS for now)
        params = job.export_params
        source = params.get("source")
        export_format = params.get("format", "csv")
        filters = params.get("filters", {})

        if source != "iceberg_email_facts":
            raise NotImplementedError(f"Export source '{source}' is not yet supported.")
        if export_format != "csv":
            raise NotImplementedError(f"Export format '{export_format}' is not yet supported.")

        self.update_state(state='PROGRESS', meta={'job_id': job_id, 'status': f'Fetching data from {source}... '})

        # 3. Fetch data (Adapt from query_iceberg_emails_duckdb)
        keywords = filters.get("keywords", [])
        # Limit fetch slightly higher than token limit to see if truncation happens
        initial_fetch_limit = token.row_limit + 50 

        fetched_data: List[Dict[str, Any]] = await query_iceberg_emails_duckdb(
            user_email=job.user_id,
            keywords=keywords,
            limit=initial_fetch_limit,
            token=token # Token passed here handles allow_columns and initial row_limit
        )

        logger.info(f"Task {self.request.id}: Fetched {len(fetched_data)} records initially.")
        self.update_state(state='PROGRESS', meta={'job_id': job_id, 'status': 'Applying token rules...'})

        # 4. Apply token rules and prepare final data
        filtered_data = []
        allowed_columns = token.allow_columns # Already applied in fetch, but used for header order
        allow_attachments = token.allow_attachments
        can_export_vectors = token.can_export_vectors
        row_limit = token.row_limit

        # Define potentially sensitive columns
        attachment_related_columns = ['attachment_ids', 'attachment_names', 'attachment_count', 'r2_keys']
        vector_related_columns = ['vector', 'embedding'] # Add any other relevant vector fields

        final_column_order = None
        # If allow_columns is defined by the token, use that as the definitive order
        if allowed_columns is not None:
             # Ensure essential ID field is present if not explicitly allowed? Decide policy.
             # For now, strictly adhere to allow_columns if set.
             final_column_order = list(allowed_columns)
             # Remove attachment/vector cols from the explicit order if disallowed
             if not allow_attachments:
                 final_column_order = [col for col in final_column_order if col not in attachment_related_columns]
             if not can_export_vectors:
                 final_column_order = [col for col in final_column_order if col not in vector_related_columns]

        for row in fetched_data:
            rows_processed += 1
            # Check row limit strictly
            if rows_exported >= row_limit:
                logger.warning(f"Task {self.request.id}: Reached token row limit ({row_limit}). Stopping export processing.")
                break

            processed_row = {}
            row_attachments_redacted = False
            row_vectors_redacted = False
            
            # Column projection and filtering happens *before* this loop in query_iceberg_emails_duckdb
            # This loop now focuses on filtering attachments/vectors from the *already projected* columns
            
            # Determine column order if not set by token.allow_columns
            if final_column_order is None:
                 final_column_order = list(row.keys()) # Use order from first row
                 # Remove sensitive columns based on flags if allow_columns was not set
                 if not allow_attachments:
                      final_column_order = [col for col in final_column_order if col not in attachment_related_columns]
                 if not can_export_vectors:
                      final_column_order = [col for col in final_column_order if col not in vector_related_columns]

            # Build the row based on the final determined column order and flags
            for col in final_column_order:
                 if col in row:
                     # Check attachments
                     if col in attachment_related_columns and not allow_attachments:
                          row_attachments_redacted = True
                          continue # Skip adding this column
                     # Check vectors
                     if col in vector_related_columns and not can_export_vectors:
                          row_vectors_redacted = True
                          continue # Skip adding this column
                     # If allowed, add to processed row
                     processed_row[col] = row[col]

            # Add the fully processed row if it's not empty
            if processed_row:
                 filtered_data.append(processed_row)
                 rows_exported += 1
                 if row_attachments_redacted:
                      attachments_redacted_count += 1
                 if row_vectors_redacted:
                      vectors_redacted_count += 1
            else:
                logger.debug(f"Task {self.request.id}: Row {rows_processed} became empty after filtering, not exporting.")

        # 5. Check if any data remains after filtering
        if not filtered_data:
            logger.warning(f"Task {self.request.id}: No data left after applying token rules for Job {job_id}.")
            error_message = "No data available for export based on the provided token's rules and filters."
            final_status = ExportJobStatus.COMPLETED_NO_DATA # Use a specific status? Or just SUCCESS with 0 rows?
            celery_state = 'SUCCESS' # Celery task succeeded, even if no data
            result_location = None # No file generated
            # Need to update DB and return early
            crud_export_job.update_job_status(
                db=db, 
                job_id=job_id, 
                status=final_status, 
                error_message=error_message, 
                result_url=result_location,
                rows_processed=rows_processed,
                rows_exported=rows_exported
            )
            self.update_state(state=celery_state, meta={'job_id': job_id, 'status': error_message, 'result_url': result_location})
            logger.info(f"Task {self.request.id}: Completed Job {job_id}. Status: {final_status}. Processed: {rows_processed}, Exported: {rows_exported}, Attachments Redacted: {attachments_redacted_count}, Vectors Redacted: {vectors_redacted_count}.")
            return {'status': final_status.value, 'message': error_message}

        logger.info(f"Task {self.request.id}: Processed {rows_processed} rows, exporting {rows_exported} rows after applying token rules.")
        self.update_state(state='PROGRESS', meta={'job_id': job_id, 'status': 'Formatting data...'})

        # 6. Format data to CSV
        output = io.StringIO()
        # Use the final_column_order determined above for the header
        writer = csv.DictWriter(output, fieldnames=final_column_order, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(filtered_data)
        csv_data = output.getvalue().encode('utf-8')
        output.close()
        logger.info(f"Task {self.request.id}: Formatted {len(filtered_data)} rows into CSV ({len(csv_data)} bytes).")

        # 7. Upload to R2
        self.update_state(state='PROGRESS', meta={'job_id': job_id, 'status': 'Uploading results...'})
        now = datetime.datetime.now(timezone.utc)
        r2_key = f"exports/{job.user_id}/{job.id}_{now.strftime('%Y%m%d%H%M%S')}.csv"
        
        # R2 upload needs careful handling in async context
        from starlette.concurrency import run_in_threadpool # Ensure imported
        await run_in_threadpool(
             r2_service.upload_fileobj, # Pass the function itself
             Fileobj=io.BytesIO(csv_data),
             Bucket=settings.R2_BUCKET_NAME,
             Key=r2_key,
             ExtraArgs={'ContentType': 'text/csv'}
        )
        result_location = f"r2://{settings.R2_BUCKET_NAME}/{r2_key}"
        logger.info(f"Task {self.request.id}: Successfully uploaded export file to {result_location}.")

        # 8. Set final status variables for success
        final_status = ExportJobStatus.COMPLETED
        error_message = None
        celery_state = 'SUCCESS'

    except Exception as e:
        job_id_exc = job_id if job else 'UNKNOWN'
        logger.error(f"Task {self.request.id}: Export failed for Job ID {job_id_exc}: {e}", exc_info=True)
        error_message = f"Export failed: {str(e)}"
        final_status = ExportJobStatus.FAILED
        celery_state = 'FAILURE'
        # Ensure result_location is None on failure
        result_location = None
        # Re-raise exception after attempting to log/update status
        # Do not raise e here, let the finally block handle status update
        pass # Error is logged, status variables are set for finally block

    finally:
        # This block ensures status is updated regardless of success or caught exceptions
        job_id_final = job_id if job else 'UNKNOWN'
        try:
            if job: # Only update if job was successfully fetched initially
                crud_export_job.update_job_status(
                    db=self.db, 
                    job_id=job.id, 
                    status=final_status, 
                    error_message=error_message, 
                    result_url=result_location,
                    # Add audit counts to the job record
                    rows_processed=rows_processed,
                    rows_exported=rows_exported
                    # Potentially add attachment/vector redaction counts here too if schema allows
                )
            self.update_state(state=celery_state, meta={'job_id': job_id_final, 'status': final_status.value, 'result_url': result_location, 'error': error_message})
            logger.info(f"Task {self.request.id}: Completed Job {job_id_final}. Final Status: {final_status}. Processed: {rows_processed}, Exported: {rows_exported}, Attachments Redacted: {attachments_redacted_count}, Vectors Redacted: {vectors_redacted_count}.")
            
            # Increment Prometheus counters (Ensure they are imported)
            # Only increment if the count is positive and we have the token info
            if attachments_redacted_count > 0 and token:
                 ATTACHMENT_REDACTIONS.labels(token_id=token.id, route="/export/task").inc(attachments_redacted_count)
            # Add similar logic for vector redactions if a specific counter exists
            # if vectors_redacted_count > 0 and token:
            #     VECTORS_REDACTED.labels(token_id=token.id, route="/export/task").inc(vectors_redacted_count)

        except Exception as final_update_error:
            logger.error(f"Task {self.request.id}: CRITICAL - Failed to update final job/task status for job {job_id_final}: {final_update_error}")
            # Task state might be incorrect if this fails

    # Return final status info
    return {
        'status': final_status.value,
        'message': error_message,
        'result_url': result_location,
        'rows_processed': rows_processed,
        'rows_exported': rows_exported,
        'attachments_redacted': attachments_redacted_count,
        'vectors_redacted': vectors_redacted_count
    } 