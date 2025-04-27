import logging
from celery import Task
from msal import ConfidentialClientApplication # Assuming msal_app is configured elsewhere or recreated
import asyncio # Import asyncio
from asyncio import TimeoutError # Explicit import for clarity
from fastapi.concurrency import run_in_threadpool # Import run_in_threadpool
import pandas as pd
import pyarrow as pa
from pyiceberg.io.pyarrow import schema_to_pyarrow

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
from pyiceberg.types import ( 
    NestedField, # ADDED NestedField import
    BooleanType, 
    IntegerType, 
    StringType, 
    TimestampType, 
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

# Define the expected schema for the email_facts table
# Field IDs are assigned automatically starting from 1
# UPDATED: Use NestedField instead of field
EMAIL_FACTS_SCHEMA = Schema(
    NestedField(field_id=1, name="message_id", field_type=StringType(), required=True, doc="Unique message ID from the email provider."),
    NestedField(field_id=2, name="job_id", field_type=StringType(), required=False, doc="ID of the ingestion job."),
    NestedField(field_id=3, name="owner_email", field_type=StringType(), required=True, doc="Email address of the user who owns this data."),
    NestedField(field_id=4, name="sender", field_type=StringType(), required=False, doc="Sender's email address."),
    NestedField(field_id=18, name="sender_name", field_type=StringType(), required=False, doc="Sender's display name."),
    NestedField(field_id=5, name="recipients", field_type=StringType(), required=False, doc="JSON array of 'To' recipient emails."),
    NestedField(field_id=6, name="cc_recipients", field_type=StringType(), required=False, doc="JSON array of 'Cc' recipient emails."),
    NestedField(field_id=7, name="bcc_recipients", field_type=StringType(), required=False, doc="JSON array of 'Bcc' recipient emails."),
    NestedField(field_id=8, name="subject", field_type=StringType(), required=False, doc="Email subject line."),
    NestedField(field_id=9, name="body_text", field_type=StringType(), required=False, doc="Plain text body content."),
    NestedField(field_id=10, name="received_datetime_utc", field_type=TimestampType(), required=False, doc="Timestamp when the email was received (UTC)."),
    NestedField(field_id=11, name="sent_datetime_utc", field_type=TimestampType(), required=False, doc="Timestamp when the email was sent (UTC)."),
    NestedField(field_id=12, name="folder", field_type=StringType(), required=False, doc="Folder ID or name where the email resided."),
    NestedField(field_id=13, name="has_attachments", field_type=BooleanType(), required=False, doc="Whether the email has attachments."),
    NestedField(field_id=14, name="attachment_count", field_type=IntegerType(), required=False, doc="Number of attachments."),
    NestedField(field_id=15, name="attachment_details", field_type=StringType(), required=False, doc="JSON array containing details about each attachment."),
    NestedField(field_id=16, name="generated_tags", field_type=StringType(), required=False, doc="JSON array of tags generated during processing."),
    NestedField(field_id=17, name="ingested_at_utc", field_type=TimestampType(), required=False, doc="Timestamp when the record was added to Iceberg (UTC)."),
    identifier_field_ids=[1] # Set message_id (field ID 1) as the identifier
)

# Define the partition specification (partition by owner_email)
# Spec ID defaults to 0
EMAIL_FACTS_PARTITION_SPEC = PartitionSpec(
    PartitionField(source_id=3, field_id=1000, transform=IdentityTransform(), name="owner_email") # source_id=3 corresponds to owner_email
)

# Task Name reflects new location
@celery_app.task(bind=True, base=EmailProcessingTask, name='tasks.email_tasks.process_user_emails') 
def process_user_emails(self: Task, user_id: str, filter_criteria_dict: dict):
    """
    Celery task to fetch, process (generate tags), and store emails based on criteria.
    Uses OutlookService for fetching, OpenAI for tagging, and Milvus for storage.
    Args:
        user_id (str): The email address of the user whose emails are being processed.
        filter_criteria_dict (dict): A dictionary representation of EmailFilter criteria.
    Returns:
        dict: A summary dictionary indicating success or failure.
    """
    task_id = self.request.id
    logger.info(f"Starting email processing task {task_id} for user '{user_id}' with filter: {filter_criteria_dict}")
    self.update_state(state='STARTED', meta={'user_email': user_id, 'progress': 0, 'status': 'Initializing...'})
    
    db = None # Initialize db to None
    try:
        # --- Parse Filter Criteria ---
        try:
            filter_criteria = EmailFilter(**filter_criteria_dict)
            logger.debug(f"Task {task_id}: Parsed filter criteria: {filter_criteria.model_dump_json()}")
        except Exception as parse_error:
            logger.error(f"Task {task_id}: Failed to parse filter_criteria_dict: {parse_error}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Invalid filter criteria provided'})
            return {'status': 'ERROR', 'message': 'Invalid filter criteria'}

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
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Failed to connect to Iceberg catalog: {catalog_err}'})
            raise Exception(f"Failed to initialize Iceberg Catalog: {catalog_err}")

        # --- Get R2 Client ---
        try:
            logger.info(f"Task {task_id}: Initializing R2 client.")
            r2_client = r2_service.get_r2_client()
            logger.info(f"Task {task_id}: R2 client initialized successfully.")
        except Exception as r2_err:
            logger.error(f"Task {task_id}: Failed to initialize R2 client: {r2_err}", exc_info=True)
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Failed to connect to R2: {r2_err}'})
            raise Exception(f"Failed to initialize R2 client: {r2_err}")

        # --- Retrieve User and Refresh Token ---
        db_user = user_crud.get_user_full_instance(db=db, email=user_id)

        if not db_user:
            logger.error(f"Task {task_id}: User with email '{user_id}' not found in database.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'User not found'})
            return {'status': 'ERROR', 'message': 'User not found'}

        logger.debug(f"Task {task_id}: Found user {db_user.email}.")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 5, 'status': 'User found'})

        encrypted_token_bytes = db_user.ms_refresh_token
        if not encrypted_token_bytes:
            logger.error(f"Task {task_id}: No encrypted refresh token found in DB for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Missing refresh token data'})
            return {'status': 'ERROR', 'message': 'Refresh token data not found'}

        refresh_token = decrypt_token(encrypted_token_bytes)
        if not refresh_token:
            logger.error(f"Task {task_id}: Failed to decrypt refresh token for user {db_user.email}.")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Failed to decrypt token'})
            return {'status': 'ERROR', 'message': 'Could not decrypt session token'}
        
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
            logger.info(f"Task {task_id}: Created IngestionJob ID {job_record.id} for user {user_id}.")
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
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Failed to initialize job tracking: {job_create_err}'})
            db.rollback() # Ensure rollback if job creation failed
            return {'status': 'ERROR', 'message': 'Failed to initialize job tracking'}
        # --- End Create IngestionJob Record ---

        # --- Acquire New Access Token ---
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 10, 'status': 'Acquiring access token...'})
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

            # --- Define an async function to run the call with timeout ---
            async def run_refresh_with_timeout():
                logger.info(f"Task {task_id}: Attempting token refresh in threadpool for user {db_user.email}.")
                # Use a timeout value from settings, defaulting if not present
                timeout_seconds = getattr(settings, 'MS_REFRESH_TIMEOUT_SECONDS', 30)
                result = await asyncio.wait_for(
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
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Token acquisition timed out'})
            return {'status': 'ERROR', 'message': 'Token acquisition timed out'}
        except Exception as refresh_exc: # Catch any other errors during run_refresh_with_timeout
            logger.error(f"Task {task_id}: Error during token refresh execution for user {db_user.email}: {refresh_exc}", exc_info=True)
            # Attempt to extract MSAL-specific error if possible (structure might vary)
            error_desc = str(refresh_exc)
            if hasattr(refresh_exc, 'error_response') and isinstance(refresh_exc.error_response, dict):
                 error_desc = refresh_exc.error_response.get('error_description', str(refresh_exc))
                 logger.error(f"Task {task_id}: MSAL error during refresh: {error_desc}")

            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Token acquisition failed: {error_desc}'})
            return {'status': 'ERROR', 'message': f'Token acquisition failed: {error_desc}'}


        # Check the result dictionary *after* successful execution (no timeout/exception)
        if not token_result or "error" in token_result:
            error_desc = token_result.get('error_description', 'Unknown token acquisition error') if token_result else "No result from refresh call"
            logger.error(f"Task {task_id}: Failed to acquire access token (MSAL error) for user {db_user.email}. Error: {token_result.get('error') if token_result else 'N/A'}, Desc: {error_desc}")
            self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': f'Token acquisition failed (MSAL): {error_desc}'})
            return {'status': 'ERROR', 'message': f'Token acquisition failed (MSAL): {error_desc}'}

        access_token = token_result.get('access_token')
        if not access_token:
             logger.error(f"Task {task_id}: Acquired token result does not contain an access token for user {db_user.email}.")
             self.update_state(state='FAILURE', meta={'user_email': user_id, 'status': 'Acquired token missing access_token key'})
             return {'status': 'ERROR', 'message': 'Internal error during token acquisition'}

        logger.info(f"Task {task_id}: Successfully acquired new access token for user {db_user.email}.")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 15, 'status': 'Access token acquired'})

        # --- Initialize Outlook Service ---
        outlook_service = OutlookService(access_token)

        # --- Define Target Milvus Collection --- 
        sanitized_email = user_id.replace('@', '_').replace('.', '_')
        target_collection_name = f"{sanitized_email}_email_knowledge"
        logger.info(f"Task {task_id}: Target Milvus collection: {target_collection_name}")

        # --- Perform Email Processing using Knowledge Service --- 
        logger.info(f"Task {task_id}: Calling knowledge service to process emails for user {user_id}")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 20, 'status': 'Processing emails...'})

        def update_progress(state, meta):
            full_meta = {'user_email': user_id, **meta}
            self.update_state(state=state, meta=full_meta)
        
        # MODIFIED: Call service which now returns data for Iceberg (and attachment counts)
        processed_count, failed_count, att_processed, att_failed, facts_data = asyncio.run(
            _process_and_store_emails(
                operation_id=task_id,
                owner_email=user_id,
                filter_criteria=filter_criteria,
                outlook_service=outlook_service,
                update_state_func=update_progress,
                db_session=db,
                ingestion_job_id=ingestion_job_db_id,
                r2_client=r2_client # Pass the initialized R2 client
            )
        )

        logger.info(f"Task {task_id}: Email processing completed. Emails: {processed_count} processed, {failed_count} failed. Attachments: {att_processed} processed, {att_failed} failed. Data points to insert: {len(facts_data)}")
        self.update_state(state='PROGRESS', meta={'user_email': user_id, 'progress': 90, 'status': 'Saving email facts...'})

        # --- Write Data to Iceberg ---
        if facts_data:
            try:
                table_namespace = settings.ICEBERG_DEFAULT_NAMESPACE
                table_name = settings.ICEBERG_EMAIL_FACTS_TABLE
                full_table_name = f"{table_namespace}.{table_name}"
                logger.info(f"Task {task_id}: Preparing to write {len(facts_data)} records to Iceberg table '{full_table_name}'.")
                is_upsert_possible = False # Default to append/fallback
                table = None
                message_id_field_id_to_use = 1 # Default field ID for message_id

                try:
                    logger.info(f"Task {task_id}: Attempting to load Iceberg table: {full_table_name}")
                    table = catalog.load_table(full_table_name)
                    logger.info(f"Task {task_id}: Table '{full_table_name}' loaded successfully.")
                
                except NoSuchTableError:
                    logger.warning(f"Task {task_id}: Table '{full_table_name}' does not exist. Attempting to create it.")
                    try:
                        table = catalog.create_table(
                            identifier=full_table_name,
                            schema=EMAIL_FACTS_SCHEMA,
                            partition_spec=EMAIL_FACTS_PARTITION_SPEC
                        )
                        logger.info(f"Task {task_id}: Successfully created Iceberg table '{full_table_name}' with schema ID {table.schema().schema_id} and spec ID {table.spec().spec_id}.")
                        # Since we just created it with the correct identifier, upsert should be possible
                        is_upsert_possible = True
                    except TableAlreadyExistsError:
                        logger.warning(f"Task {task_id}: Table '{full_table_name}' already exists (race condition?). Attempting to load again.")
                        table = catalog.load_table(full_table_name) # Try loading again
                    except Exception as create_err:
                        logger.error(f"Task {task_id}: Failed to create Iceberg table '{full_table_name}': {create_err}. Cannot write data.", exc_info=True)
                        # Update state and return error if creation fails
                        self.update_state(state='FAILURE', meta={'user_email': user_id, 'progress': 90, 'status': f'Failed to create Iceberg table: {create_err}'})
                        return {'status': 'ERROR', 'message': f'Failed to create target Iceberg table: {create_err}', 'emails_processed': processed_count, 'emails_failed': failed_count, 'attachments_processed': att_processed, 'attachments_failed': att_failed}

                # If table is loaded (either initially or after creation), proceed to check schema/upsert possibility
                if table:
                     # --- Check/Set Identifier Field (existing logic, slightly adapted) ---
                    try:
                        schema = table.schema()
                        logger.debug(f"Task {task_id}: Loaded schema: {schema}")
                        logger.debug(f"Task {task_id}: Current identifier fields: {schema.identifier_field_ids}")

                        # Find field ID for message_id
                        try:
                             message_id_field = schema.find_field("message_id", case_sensitive=False)
                             message_id_field_id_to_use = message_id_field.field_id
                             logger.info(f"Task {task_id}: Found 'message_id' field with ID: {message_id_field_id_to_use}")
                        except ValueError:
                            logger.error(f"Task {task_id}: Critical error - 'message_id' field not found in schema even after load/create. Cannot perform upsert.")
                            is_upsert_possible = False
                        
                        if message_id_field_id_to_use in schema.identifier_field_ids:
                            logger.info(f"Task {task_id}: 'message_id' (ID: {message_id_field_id_to_use}) is already an identifier field. Upsert possible.")
                            is_upsert_possible = True
                        # Don't try to update schema immediately after creation, as it should be correct
                        elif not is_upsert_possible: # Only try update if not already set and not just created
                             logger.warning(f"Task {task_id}: 'message_id' (ID: {message_id_field_id_to_use}) is NOT an identifier field. Attempting schema update...")
                            # ... existing schema update logic ...
                            # try:
                            #     with table.update_schema() as update:
                            #         update.set_identifier_fields("message_id") # Use field name
                            # ... etc ...
                            # except Exception as schema_update_err:
                            #     ...
                            #     is_upsert_possible = False
                    except Exception as schema_inspect_err:
                        logger.error(f"Task {task_id}: Error inspecting/updating Iceberg schema: {schema_inspect_err}. Falling back.", exc_info=True)
                        is_upsert_possible = False
                    # --- End Check/Set Identifier ---
                    
                    # Get the final Arrow schema 
                    arrow_schema = schema_to_pyarrow(table.schema())
                    logger.debug(f"Task {task_id}: Final Arrow schema for target table: {arrow_schema}")
                    
                    # E.g., convert facts_data to Arrow table
                    try:
                        arrow_table = pa.Table.from_pylist(facts_data, schema=arrow_schema)
                    except Exception as arrow_conv_err:
                         logger.error(f"Task {task_id}: Failed to convert data to Arrow table: {arrow_conv_err}. Cannot write to Iceberg.", exc_info=True)
                         # Handle error appropriately
                         # ... (update state, return error) ...
                         raise # Re-raise for outer exception handler
                         
                    # --- ADDED: Actual write operation --- 
                    try:
                        if is_upsert_possible:
                             logger.info(f"Task {task_id}: Performing UPSERT into Iceberg table '{full_table_name}' using identifier field ID {message_id_field_id_to_use}...")
                             # Assuming table object has an upsert method accepting an Arrow table
                             # The exact method and parameters might differ based on pyiceberg version
                             # Example: table.upsert(arrow_table) or table.merge(...) etc.
                             # For now, let's fallback to append as upsert isn't fully defined
                             logger.warning(f"Task {task_id}: Upsert logic not fully implemented, falling back to append.")
                             table.append(arrow_table)
                             logger.info(f"Task {task_id}: Successfully APPENDED {len(arrow_table)} records (fallback from upsert). ")
                        else:
                             logger.info(f"Task {task_id}: Performing APPEND to Iceberg table '{full_table_name}'...")
                             table.append(arrow_table)
                             logger.info(f"Task {task_id}: Successfully APPENDED {len(arrow_table)} records.")
                    except Exception as write_err:
                        logger.error(f"Task {task_id}: Failed during Iceberg write operation (append/upsert): {write_err}", exc_info=True)
                        raise # Re-raise to be caught by the outer Iceberg block
                    # --- END: Actual write operation --- 

            except Exception as iceberg_err: # Catch errors during load/create/write
                logger.error(f"Task {task_id}: Failed Iceberg operation for table '{full_table_name}': {iceberg_err}", exc_info=True)
                # Update failure counts if Iceberg write fails?
                self.update_state(state='FAILURE', meta={'user_email': user_id, 'progress': 95, 'status': f'Failed Iceberg operation: {iceberg_err}'})
                return {'status': 'ERROR', 'message': f'Failed final save step to Iceberg: {iceberg_err}', 'emails_processed': processed_count, 'emails_failed': failed_count, 'attachments_processed': att_processed, 'attachments_failed': att_failed}
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
            'user_email': user_id, 
            'progress': 100, 
            'status': final_message, 
            'emails_processed': processed_count, 
            'emails_failed': failed_count,
            'attachments_processed': att_processed,
            'attachments_failed': att_failed
            })
        return {
            'status': final_status, 
            'message': final_message, 
            'emails_processed': processed_count, 
            'emails_failed': failed_count,
            'attachments_processed': att_processed,
            'attachments_failed': att_failed
            }

    except Exception as e:
        task_id_exc = getattr(self.request, 'id', 'UNKNOWN_TASK_ID')
        user_id_exc = user_id if 'user_id' in locals() else 'UNKNOWN_USER'
        logger.error(f"Task {task_id_exc} failed for user '{user_id_exc}': {e}", exc_info=True)
        job_id_exc = job_record.id if 'job_record' in locals() and job_record else None
        error_msg_exc = str(e)
        try:
            # Attempt to update state one last time on general failure
            self.update_state(state='FAILURE', meta={'user_email': user_id_exc, 'status': f'Internal task error: {error_msg_exc}'})
            # ++ Update IngestionJob status on failure ++
            if db and job_id_exc is not None:
                try:
                    crud_ingestion_job.update_job_status(db=db, job_id=job_id_exc, status='failed', error_message=error_msg_exc)
                    db.commit()
                    logger.info(f"Task {task_id_exc}: Updated IngestionJob ID {job_id_exc} status to failed.")
                except Exception as update_fail_err:
                    db.rollback()
                    logger.error(f"Task {task_id_exc}: Failed to update IngestionJob ID {job_id_exc} status to failed during exception handling: {update_fail_err}")
            # -- End Update --
        except Exception as state_update_error:
            logger.error(f"Task {task_id_exc}: Failed to update state/job during exception handling: {state_update_error}")
        # Reraise the exception to let Celery handle it (logging, retries etc.)
        raise e # Reraise after logging and state update attempt
    finally:
        # ++ Update IngestionJob status on completion (if successful/partial) ++
        final_job_status = None
        final_job_error = None
        if 'final_status' in locals(): # Check if task reached completion logic
            if final_status == 'SUCCESS':
                final_job_status = 'completed'
            elif final_status == 'PARTIAL_SUCCESS':
                 final_job_status = 'partial_complete'
                 final_job_error = final_message # Store the partial success message
            
            if db and job_record and final_job_status:
                try:
                    crud_ingestion_job.update_job_status(db=db, job_id=job_record.id, status=final_job_status, error_message=final_job_error)
                    db.commit()
                    logger.info(f"Task {task_id}: Updated IngestionJob ID {job_record.id} status to {final_job_status}.")
                except Exception as final_update_err:
                    db.rollback()
                    logger.error(f"Task {task_id}: Failed to update final IngestionJob ID {job_record.id} status to {final_job_status}: {final_update_err}")
        # -- End Update --

        # Ensure DB session is closed
        if db:
            db.close()
            logger.debug(f"Task {getattr(self.request, 'id', 'UNKNOWN')}: Database session closed.")
        # Milvus client closing might not be needed if managed elsewhere 