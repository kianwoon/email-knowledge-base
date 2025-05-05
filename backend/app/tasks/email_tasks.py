import logging
from celery import Task
from msal import ConfidentialClientApplication # Assuming msal_app is configured elsewhere or recreated
import asyncio # Import asyncio
from asyncio import TimeoutError # Explicit import for clarity
from fastapi.concurrency import run_in_threadpool # Import run_in_threadpool
import pandas as pd
import pyarrow as pa
from pyiceberg.io.pyarrow import schema_to_pyarrow
from typing import List, Dict, Tuple, Any
from datetime import datetime
import json

# Remove Qdrant Imports
# from qdrant_client import QdrantClient, models
# from qdrant_client.http.exceptions import UnexpectedResponse
# Import Milvus
from pymilvus import MilvusClient

from app.celery_app import celery_app
# from ..core.config import settings # OLD Relative import (wrong path)
from ..config import settings # CORRECTED Relative import
from app.db.session import SessionLocal # Assuming SessionLocal is available for creating new sessions
from app.crud import user_crud, crud_ingestion_job # Assuming user_crud and crud_ingestion_job are available
from app.services.outlook import OutlookService # Assuming OutlookService is available
from app.models.email import EmailFilter # Import EmailFilter
# Import the new service function and Milvus client getter
from app.services.knowledge_service import _process_and_store_emails
from app.db.milvus_client import get_milvus_client, ensure_collection_exists
# Add other necessary imports for email processing (e.g., Milvus client, analysis service)
# from app.services.qdrant_service import QdrantService
# from app.services.analysis_service import AnalysisService
# --- Import for manual encryption/decryption --- 
from app.utils.security import decrypt_token
# --- End Import ---
from app.schemas.ingestion_job import IngestionJobCreate # Import schema

# ADDED: Import PyIceberg REST Catalog from diff
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.exceptions import NamespaceAlreadyExistsError, TableAlreadyExistsError, NoSuchTableError # ADDED Iceberg exceptions from diff
# ADD PyIceberg types and schema helpers
from pyiceberg.schema import Schema # REMOVED field import
from pyiceberg.expressions import EqualTo, In # ADDED In import
from pyiceberg.types import ( 
    NestedField, # ADDED NestedField import
    BooleanType, 
    IntegerType, 
    StringType, 
    TimestampType, 
    StructType,
    ListType,
) 
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform

from app.services import r2_service # Added R2 service import

logger = logging.getLogger(__name__)

# Helper function to get a new MSAL app instance if needed within the task
# Or potentially pass the configured msal_app if safe and feasible
def get_msal_app():
    return ConfidentialClientApplication(
        settings.MS_CLIENT_ID,
        authority=settings.MS_AUTHORITY,
        client_credential=settings.MS_CLIENT_SECRET,
        # token_cache=... # Consider token caching strategy for workers if applicable
    )

class EmailProcessingTask(Task):
    """Custom Task class for potential shared logic or state"""
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f'{self.name}[{task_id}] failed: {exc}', exc_info=exc)
        # Add custom failure logic if needed (e.g., notification, specific cleanup)
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f'{self.name}[{task_id}] succeeded. Result: {retval}')
        # Add custom success logic if needed
        super().on_success(retval, task_id, args, kwargs)

    def _write_to_iceberg(self, catalog: RestCatalog, table_name: str, facts: List[Dict[str, Any]], job_id: str) -> Tuple[int, int]:
        """
        Writes email facts to Iceberg table, ensuring data for the specific owner is overwritten
        without affecting other owners.
        Returns tuple of (success_count, failure_count)
        """
        success_count = 0
        failure_count = 0

        if not facts:
            logger.info(f"Task {job_id}: No facts provided to write to Iceberg table '{table_name}'. Skipping.")
            return (0, 0)

        # --- Determine the owner email for this batch --- 
        try:
            # Assuming all facts in the list belong to the same owner
            owner_email_for_batch = facts[0].get('owner_email')
            if not owner_email_for_batch or not isinstance(owner_email_for_batch, str):
                 raise ValueError("Missing or invalid 'owner_email' in the first fact record.")
            # Optional: Verify all facts have the same owner if needed
            # all_owners = {fact.get('owner_email') for fact in facts}
            # if len(all_owners) > 1 or owner_email_for_batch not in all_owners:
            #     raise ValueError(f"Multiple or inconsistent owner emails found in the batch for job {job_id}.")
            logger.info(f"Task {job_id}: Preparing to write/overwrite data for owner '{owner_email_for_batch}' in table '{table_name}'.")
        except (IndexError, ValueError, KeyError) as owner_err:
            logger.error(f"Task {job_id}: Could not determine owner email from facts data: {owner_err}. Cannot write to Iceberg.", exc_info=True)
            return (0, len(facts))

        try:
            # Get or create the table
            try:
                table = catalog.load_table(table_name)
                # --- Log loaded table partition spec ---
                logger.info(f"Task {job_id}: Loaded table partition spec: {table.spec()}")
            except NoSuchTableError:
                logger.info(f"Task {job_id}: Creating new Iceberg table '{table_name}'")
                table = catalog.create_table(
                    identifier=table_name,
                    schema=EMAIL_FACTS_SCHEMA,
                    partition_spec=EMAIL_FACTS_PARTITION_SPEC
                )
                logger.info(f"Task {job_id}: Created Iceberg table '{table_name}' with flattened schema.")

            # Convert list of dictionaries to Arrow Table
            logger.info(f"Task {job_id}: Generating Arrow schema from EMAIL_FACTS_SCHEMA constant.")
            arrow_schema = schema_to_pyarrow(EMAIL_FACTS_SCHEMA)
            arrow_table = pa.Table.from_pylist(facts, schema=arrow_schema)
            logger.debug(f"Task {job_id}: Converted {len(facts)} records to Arrow table for owner '{owner_email_for_batch}'.")

            # --- Deduplicate input data based on message_id before upsert ---
            if arrow_table.num_rows > 0:
                initial_rows = arrow_table.num_rows
                df = arrow_table.to_pandas()
                # Corrected: Use 'message_id' for deduplication, matching the table identifier
                df.drop_duplicates(subset=['message_id'], keep='first', inplace=True) 
                final_rows = len(df)
                if final_rows < initial_rows:
                    # Corrected log message
                    logger.warning(f"Task {job_id}: Deduplicated input data for upsert based on 'message_id'. Original rows: {initial_rows}, Final rows: {final_rows}.")
                arrow_table = pa.Table.from_pandas(df, schema=arrow_schema, preserve_index=False)
            # --- End Deduplication ---

            # --- Explicitly check the loaded table schema's identifier --- 
            loaded_schema = table.schema()
            logger.info(f"Task {job_id}: Loaded table schema identifier field IDs: {loaded_schema.identifier_field_ids}")

            # --- Use Upsert (Reverted from Overwrite) --- 
            logger.info(f"Task {job_id}: Performing UPSERT into Iceberg table '{table_name}' for owner '{owner_email_for_batch}' using identifier field ID {table.schema().identifier_field_ids}.")
            try:
                result = table.upsert(arrow_table)
                logger.debug(f"Task {job_id}: Upsert operation returned: {result}")
                # Use arrow_table.num_rows as it accounts for potential deduplication
                success_count = arrow_table.num_rows 
                logger.info(f"Task {job_id}: Upsert operation successful for owner '{owner_email_for_batch}', batch of {success_count} records.")
            except Exception as upsert_err:
                logger.error(f"Task {job_id}: Error during Iceberg UPSERT operation: {upsert_err}", exc_info=True)
                 # Count failures based on input rows before potential deduplication?
                 # Using arrow_table.num_rows might be more accurate here too
                failure_count = arrow_table.num_rows 
                success_count = 0
            # --- End Upsert ---

        except Exception as table_error:
            logger.error(f"Task {job_id}: Iceberg table operation failed for owner '{owner_email_for_batch}' in '{table_name}': {table_error}", exc_info=True)
            failure_count = len(facts)
            success_count = 0

        return (success_count, failure_count)

# Define the SIMPLIFIED structure for quoted email details (Raw Text approach)
# Corrected field IDs to match actual table schema
QUOTED_DETAIL_STRUCT = StructType(
    NestedField(field_id=27, name="quoted_raw_text", field_type=StringType(), required=False, doc="Raw text content of the quoted section."), # Changed ID from 701 to 27
    NestedField(field_id=28, name="quoted_depth", field_type=IntegerType(), required=False, doc="Nesting level of the quote (0 = direct reply, 1 = quote of a reply, etc.).") # Changed ID from 702 to 28
)

# Define the expected schema for the email_facts table
# FLATTENED MODEL - Reflects schema after evolution script
EMAIL_FACTS_SCHEMA = Schema(
    # --- Core Fields ---
    NestedField(field_id=1, name="message_id", field_type=StringType(), required=True, doc="Unique message ID or synthetic quote ID."),
    NestedField(field_id=2, name="job_id", field_type=StringType(), required=False, doc="ID of the ingestion job."),
    NestedField(field_id=3, name="owner_email", field_type=StringType(), required=True, doc="Email address of the user who owns this data."),
    # --- Parent Email Fields (duplicated for quotes) ---
    NestedField(field_id=4, name="sender", field_type=StringType(), required=False, doc="Sender's email address."),
    NestedField(field_id=5, name="sender_name", field_type=StringType(), required=False, doc="Sender's display name."),
    NestedField(field_id=6, name="recipients", field_type=StringType(), required=False, doc="JSON array of 'To' recipient emails."),
    NestedField(field_id=7, name="cc_recipients", field_type=StringType(), required=False, doc="JSON array of 'Cc' recipient emails."),
    NestedField(field_id=8, name="bcc_recipients", field_type=StringType(), required=False, doc="JSON array of 'Bcc' recipient emails."),
    NestedField(field_id=9, name="subject", field_type=StringType(), required=False, doc="Email subject line."),
    # --- Row-Specific Content / Metadata (Adjusted Order) ---
    NestedField(field_id=10, name="body_text", field_type=StringType(), required=False, doc="Plain text body content (of the parent email, null for quotes)."),
    # --- Parent Email Fields (Continued - Adjusted Order) ---
    NestedField(field_id=11, name="received_datetime_utc", field_type=TimestampType(), required=False, doc="Timestamp when the email was received (UTC)."),
    NestedField(field_id=12, name="sent_datetime_utc", field_type=TimestampType(), required=False, doc="Timestamp when the email was sent (UTC)."),
    NestedField(field_id=13, name="folder", field_type=StringType(), required=False, doc="Folder ID or name where the email resided."),
    # --- General Metadata (Adjusted Order) ---
    NestedField(field_id=14, name="has_attachments", field_type=BooleanType(), required=False, doc="Whether the email has attachments (applies to parent)."),
    NestedField(field_id=15, name="attachment_count", field_type=IntegerType(), required=False, doc="Number of attachments (applies to parent)."),
    NestedField(field_id=16, name="attachment_details", field_type=StringType(), required=False, doc="JSON array containing details about each attachment (applies to parent)."),
    NestedField(field_id=17, name="generated_tags", field_type=StringType(), required=False, doc="JSON array of tags generated during processing (applies to parent)."),
    NestedField(field_id=18, name="ingested_at_utc", field_type=TimestampType(), required=False, doc="Timestamp when the record was added to Iceberg (UTC)."),
    # --- Parent Email Fields (Continued - Adjusted Order) ---
    NestedField(field_id=19, name="conversation_id", field_type=StringType(), required=False, doc="ID that groups related emails in a thread."),
    # --- Row-Specific Content / Metadata (Adjusted Order) ---
    NestedField(field_id=20, name="thread_position", field_type=IntegerType(), required=False, doc="Position of parent message in thread (null for quotes)."),
    NestedField(field_id=21, name="granularity", field_type=StringType(), required=False, doc="Type of row: 'full_message' or 'quoted_message'."),
    NestedField(field_id=22, name="quoted_email_count", field_type=IntegerType(), required=False, doc="Total quotes in parent email (null for quotes)."),
    NestedField(field_id=23, name="quoted_sender_domains", field_type=StringType(), required=False, doc="JSON array of sender domains in parent's quotes (null for quotes)."),
    NestedField(field_id=24, name="is_quoted_only", field_type=BooleanType(), required=False, doc="If parent email is only quotes (null for quotes)."),
    # --- Quote-Specific Fields (null for parent) - Use IDs from evolution script ---
    NestedField(field_id=29, name="quoted_raw_text", field_type=StringType(), required=False, doc="Raw text content of this specific quoted section (null for parent)."), # ID 29 from evolution
    NestedField(field_id=30, name="quoted_depth", field_type=IntegerType(), required=False, doc="Nesting level of this specific quote (null for parent)."), # ID 30 from evolution
    # Removed row_id (field_id=481) as it's not in the target table schema
    # --- Identifier ---
    # Use message_id (ID 1) as indicated by UPSERT log message
    identifier_field_ids=[1]
)

# Define the partition specification (partition by owner_email)
# Spec ID defaults to 0
EMAIL_FACTS_PARTITION_SPEC = PartitionSpec(
    PartitionField(source_id=3, field_id=1000, transform=IdentityTransform(), name="owner_email") # source_id=3 corresponds to owner_email
)

# Task Name reflects new location
@celery_app.task(bind=True, base=EmailProcessingTask, name='tasks.email_tasks.process_user_emails') 
def process_user_emails(
    self: EmailProcessingTask, 
    user_id: str, 
    user_email: str, 
    folder_id: str, 
    from_date: datetime
) -> int:
    """
    Celery task to fetch, process (generate tags), and store emails based on criteria.
    Uses OutlookService for fetching, OpenAI for tagging, and Milvus for storage.
    
    Args:
        user_id (str): The ID of the user whose emails are being processed.
        user_email (str): The email address of the user.
        folder_id (str): The ID of the folder to process.
        from_date (datetime): Process emails from this date onward.
        
    Returns:
        int: Number of emails processed
    """
    task_id = self.request.id
    logger.info(f"Starting email processing task {task_id} for user '{user_id}' with folder: {folder_id}, from_date: {from_date}")
    self.update_state(state='STARTED', meta={'user_email': user_email, 'progress': 0, 'status': 'Initializing...'})
    
    # Convert the parameters to the filter_criteria_dict format expected by the rest of the function
    filter_criteria_dict = {
        "folder_id": folder_id,
        "start_date": from_date.strftime("%Y-%m-%d") if from_date else None
    }
    
    db = None # Initialize db to None
    processed_count = 0
    
    try:
        # --- Parse Filter Criteria ---
        try:
            filter_criteria = EmailFilter(**filter_criteria_dict)
            logger.debug(f"Task {task_id}: Parsed filter criteria: {filter_criteria.model_dump_json()}")
        except Exception as parse_error:
            logger.error(f"Task {task_id}: Failed to parse filter_criteria_dict: {parse_error}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': 'Invalid filter criteria provided'})
            return processed_count

        # --- Get DB Session & Milvus Client ---
        db = SessionLocal()
        if not db:
             raise Exception("Could not create database session.")
        logger.debug(f"Task {task_id}: Database session created.")

        # --- Initialize Iceberg REST Catalog ---
        try:
            logger.info(f"Task {task_id}: Initializing Iceberg REST Catalog.")
            # Define catalog properties dictionary including the downcast setting
            catalog_props = {
                "name": "r2_catalog_task_final", # Changed name slightly for certainty
                "uri": settings.R2_CATALOG_URI, # CORRECTED: Use R2_CATALOG_URI
                "warehouse": settings.R2_CATALOG_WAREHOUSE, # CORRECTED: Use R2_CATALOG_WAREHOUSE
                "token": settings.R2_CATALOG_TOKEN, # CORRECTED: Use R2_CATALOG_TOKEN
                # Ensure nanosecond timestamps are downcasted to microseconds for compatibility
                "pyiceberg.io.pyarrow.downcast-ns-timestamp-to-us-on-write": True
            }
            catalog = RestCatalog(**catalog_props) # Initialize with the full properties dict
            logger.debug(f"Catalog connection details - URI: {settings.R2_CATALOG_URI}, Warehouse: {settings.R2_CATALOG_WAREHOUSE}") # Add debug log
            logger.info(f"Task {task_id}: Iceberg REST Catalog initialized successfully.")
        except Exception as catalog_err:
            logger.error(f"Task {task_id}: Failed to initialize Iceberg REST Catalog: {catalog_err}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': f'Failed to connect to Iceberg catalog: {catalog_err}'})
            raise Exception(f"Failed to initialize Iceberg Catalog: {catalog_err}")

        # --- Get R2 Client ---
        try:
            logger.info(f"Task {task_id}: Initializing R2 client.")
            r2_client = r2_service.get_r2_client()
            logger.info(f"Task {task_id}: R2 client initialized successfully.")
        except Exception as r2_err:
            logger.error(f"Task {task_id}: Failed to initialize R2 client: {r2_err}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': f'Failed to connect to R2: {r2_err}'})
            raise Exception(f"Failed to initialize R2 client: {r2_err}")

        # --- Retrieve User and Refresh Token ---
        db_user = user_crud.get_user_full_instance(db=db, email=user_email)

        if not db_user:
            logger.error(f"Task {task_id}: User with email '{user_email}' not found in database.")
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': 'User not found'})
            return processed_count

        logger.debug(f"Task {task_id}: Found user {db_user.email}.")
        self.update_state(state='PROGRESS', meta={'user_email': user_email, 'progress': 5, 'status': 'User found'})

        encrypted_token_bytes = db_user.ms_refresh_token
        if not encrypted_token_bytes:
            logger.error(f"Task {task_id}: No encrypted refresh token found in DB for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': 'Missing refresh token data'})
            return processed_count

        refresh_token = decrypt_token(encrypted_token_bytes)
        if not refresh_token:
            logger.error(f"Task {task_id}: Failed to decrypt refresh token for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': 'Failed to decrypt token'})
            return processed_count
        
        logger.debug(f"Task {task_id}: Refresh token retrieved and decrypted for user {db_user.email}.")

        # +++ Create IngestionJob Record +++
        job_record = None
        try:
            job_schema = IngestionJobCreate(
                source_type='email',
                job_details=filter_criteria_dict # Store the original filter dict
            )
            job_record = crud_ingestion_job.create_ingestion_job(db=db, job_in=job_schema, user_id=user_id)
            if not job_record:
                raise Exception("CRUD function failed to create IngestionJob record.")
            logger.info(f"Task {task_id}: Created IngestionJob ID {job_record.id} for user {user_email}.")
            # Immediately update status to processing and link Celery task ID
            updated_job = crud_ingestion_job.update_job_status(
                db=db, 
                job_id=job_record.id, 
                status='processing', 
                celery_task_id=task_id
            )
            if not updated_job:
                raise Exception(f"Failed to update IngestionJob ID {job_record.id} status to processing.")
            db.commit() # Commit job creation and initial status update
            logger.info(f"Task {task_id}: Updated IngestionJob ID {job_record.id} status to processing.")
            ingestion_job_db_id = job_record.id # Store the integer ID
        except Exception as job_create_err:
            logger.error(f"Task {task_id}: Failed to create/update initial IngestionJob record: {job_create_err}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': f'Failed to initialize job tracking: {job_create_err}'})
            db.rollback() # Ensure rollback if job creation failed
            return processed_count
        # --- End Create IngestionJob Record ---

        # --- Acquire New Access Token ---
        self.update_state(state='PROGRESS', meta={'user_email': user_email, 'progress': 10, 'status': 'Acquiring access token...'})
        msal_instance = get_msal_app()

        reserved_scopes = {'openid', 'profile', 'offline_access'}
        required_scopes = [s for s in settings.MS_SCOPE if s not in reserved_scopes]
        logger.debug(f"Task {task_id}: Requesting access token with filtered scopes: {required_scopes}")

        token_result = None
        try:
            # Define the blocking function call
            refresh_call = lambda: msal_instance.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=required_scopes
            )

            # RESTORED: Inner async function and asyncio.run() for token refresh
            # --- Define an async function to run the call with timeout --- 
            async def run_refresh_with_timeout():
                logger.info(f"Task {task_id}: Attempting token refresh in threadpool for user {db_user.email}.")
                timeout_seconds = getattr(settings, 'MS_REFRESH_TIMEOUT_SECONDS', 30)
                result = await asyncio.wait_for( # await within async func
                    run_in_threadpool(refresh_call), 
                    timeout=timeout_seconds
                )
                logger.info(f"Task {task_id}: Token refresh call completed successfully for user {db_user.email}.")
                return result

            # --- Run the async function using asyncio.run() --- 
            token_result = asyncio.run(run_refresh_with_timeout())
            # --- End wrapped call ---

        except TimeoutError: # Catch timeout specifically
            timeout_seconds = getattr(settings, 'MS_REFRESH_TIMEOUT_SECONDS', 30)
            logger.error(f"Task {task_id}: Timeout ({timeout_seconds}s) occurred while acquiring access token for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': 'Token acquisition timed out'})
            return processed_count
        except Exception as refresh_exc: # Catch any other errors during run_refresh_with_timeout
            logger.error(f"Task {task_id}: Error during token refresh execution for user {db_user.email}: {refresh_exc}", exc_info=True)
            # Attempt to extract MSAL-specific error if possible (structure might vary)
            error_desc = str(refresh_exc)
            if hasattr(refresh_exc, 'error_response') and isinstance(refresh_exc.error_response, dict):
                 error_desc = refresh_exc.error_response.get('error_description', str(refresh_exc))
                 logger.error(f"Task {task_id}: MSAL error during refresh: {error_desc}")

            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': f'Token acquisition failed: {error_desc}'})
            return processed_count


        # Check the result dictionary *after* successful execution (no timeout/exception)
        if not token_result or "error" in token_result:
            error_desc = token_result.get('error_description', 'Unknown token acquisition error') if token_result else "No result from refresh call"
            logger.error(f"Task {task_id}: Failed to acquire access token (MSAL error) for user {db_user.email}. Error: {token_result.get('error') if token_result else 'N/A'}, Desc: {error_desc}")
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': f'Token acquisition failed (MSAL): {error_desc}'})
            return processed_count

        access_token = token_result.get('access_token')
        if not access_token:
             logger.error(f"Task {task_id}: Acquired token result does not contain an access token for user {db_user.email}.")
             self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': 'Acquired token missing access_token key'})
             return processed_count

        logger.info(f"Task {task_id}: Successfully acquired new access token for user {db_user.email}.")
        self.update_state(state='PROGRESS', meta={'user_email': user_email, 'progress': 15, 'status': 'Access token acquired'})

        # --- Initialize Outlook Service ---
        outlook_service = OutlookService(access_token)

        # --- Define Target Milvus Collection Name ---
        sanitized_email = user_email.replace('@', '_').replace('.', '_')
        # !!! IMPORTANT: Make sure this suffix matches the one used elsewhere (e.g., in embedder.py if it overrides default) !!!
        target_collection_name = f"{sanitized_email}_knowledge_base_bm" 
        logger.info(f"Task {task_id}: Target Milvus collection: {target_collection_name}")

        # --- Ensure Milvus Collection Exists ---
        try:
            logger.info(f"Task {task_id}: Initializing Milvus client.")
            milvus_client = get_milvus_client() # Get the client instance
            # Determine the correct embedding dimension
            # Assuming DENSE_EMBEDDING_DIMENSION holds the dimension for the primary vector field
            embedding_dim = settings.DENSE_EMBEDDING_DIMENSION
            if not isinstance(embedding_dim, int) or embedding_dim <= 0:
                raise ValueError(f"Invalid DENSE_EMBEDDING_DIMENSION found in settings: {embedding_dim}")
            logger.info(f"Task {task_id}: Ensuring Milvus collection '{target_collection_name}' exists with dimension {embedding_dim}.")
            ensure_collection_exists(
                client=milvus_client,
                collection_name=target_collection_name,
                dim=embedding_dim
            )
            logger.info(f"Task {task_id}: Milvus collection check/creation successful for '{target_collection_name}'.")
        except Exception as milvus_err:
            logger.error(f"Task {task_id}: Failed during Milvus initialization or collection check: {milvus_err}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_email, 'status': f'Failed Milvus setup: {milvus_err}'})
            raise Exception(f"Failed Milvus setup: {milvus_err}") # Reraise to stop the task

        # --- Perform Email Processing using Knowledge Service --- 
        logger.info(f"Task {task_id}: Calling knowledge service to process emails for user {user_email}")
        self.update_state(state='PROGRESS', meta={'user_email': user_email, 'progress': 20, 'status': 'Processing emails...'})

        def update_progress(state, meta):
            full_meta = {'user_email': user_email, **meta}
            self.update_state(state=state, meta=full_meta)
        
        # MODIFIED: Call service which now returns data for Iceberg (and attachment counts)
        # RESTORED: asyncio.run() for the main processing call
        processed_count, failed_count, att_processed, att_failed, facts_data = asyncio.run(
            _process_and_store_emails(
                operation_id=task_id,
                owner_email=user_email,
                filter_criteria=filter_criteria,
                outlook_service=outlook_service,
                update_state_func=update_progress,
                db_session=db,
                ingestion_job_id=ingestion_job_db_id,
                r2_client=r2_client # Pass the initialized R2 client
            )
        )

        logger.info(f"Task {task_id}: Email processing completed. Emails: {processed_count} processed, {failed_count} failed. Attachments: {att_processed} processed, {att_failed} failed. Data points to insert: {len(facts_data)}")
        self.update_state(state='PROGRESS', meta={'user_email': user_email, 'progress': 90, 'status': 'Saving email facts...'})

        # --- Write Data to Iceberg ---
        if facts_data:
            try:
                table_namespace = settings.ICEBERG_DEFAULT_NAMESPACE
                table_name = settings.ICEBERG_EMAIL_FACTS_TABLE
                full_table_name = f"{table_namespace}.{table_name}"
                logger.info(f"Task {task_id}: Preparing to write/overwrite {len(facts_data)} records to Iceberg table '{full_table_name}'.")

                # *** Call the method correctly via self ***
                iceberg_success_count, iceberg_failure_count = self._write_to_iceberg(
                    catalog=catalog,
                    table_name=full_table_name,
                    facts=facts_data,
                    job_id=task_id # Pass task_id as job_id for logging within the method
                )
                
                if iceberg_failure_count > 0:
                    logger.error(f"Task {task_id}: {iceberg_failure_count}/{len(facts_data)} records failed during Iceberg write.")
                    # Decide if this constitutes a task failure or partial success
                    # For now, we'll let the final status check handle it, but log the error
                else:
                    logger.info(f"Task {task_id}: Successfully wrote/overwrote {iceberg_success_count} records to Iceberg.")

            except Exception as iceberg_err: # Catch errors during the call to _write_to_iceberg or setup
                logger.error(f"Task {task_id}: Failed Iceberg operation for table '{full_table_name}': {iceberg_err}", exc_info=True)
                self.update_state(state='FAILURE', meta={'user_email': user_email, 'progress': 95, 'status': f'Failed Iceberg operation: {iceberg_err}'})
                # Include existing counts in the return message
                return processed_count
        else:
            logger.warning(f"Task {task_id}: No data points were generated by the processing service, nothing to write to Iceberg.")

        # --- Task Completion ---
        final_status = 'SUCCESS'
        final_message = f"Email processing completed. Emails: {processed_count} processed, {failed_count} failed. Attachments: {att_processed} processed, {att_failed} failed."
        if failed_count > 0 or att_failed > 0:
             final_status = 'PARTIAL_SUCCESS'
             logger.warning(f"Task {task_id}: Completed with {failed_count} email failures and {att_failed} attachment failures.")
        
        logger.info(f"Task {task_id}: {final_message}")
        self.update_state(state='SUCCESS', meta={
            'user_email': user_email, 
            'progress': 100, 
            'status': final_message, 
            'emails_processed': processed_count, 
            'emails_failed': failed_count,
            'attachments_processed': att_processed,
            'attachments_failed': att_failed
            })
        return processed_count

    except Exception as e:
        logger.error(f"Error processing emails: {str(e)}")
        return processed_count
    finally:
        if db:
            db.close()
        # Milvus client closing might not be needed if managed elsewhere 