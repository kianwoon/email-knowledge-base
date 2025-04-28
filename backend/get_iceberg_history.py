#!/usr/bin/env python

import os
import sys
import logging
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError, NoSuchNamespaceError
from pyiceberg.table import Table
from pyiceberg.table import Snapshot
from datetime import datetime
from dotenv import load_dotenv
import traceback # For more detailed error logging

# Setup logging early
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _get_snapshot_data_files(snapshot: Snapshot, table_io) -> set:
    """Helper function to get a set of data file paths from a snapshot's manifests."""
    try:
        # Iterate through manifests and collect data file paths
        files = set()
        for manifest in snapshot.manifests(table_io):
            for file_entry in manifest.fetch_manifest_entry(table_io):
                 # Assuming file_entry has a 'file_path' attribute or similar access method
                 # Adjust based on actual structure if needed
                 if hasattr(file_entry, 'file_path'):
                     files.add(file_entry.file_path)
                 elif hasattr(file_entry, 'data_file') and hasattr(file_entry.data_file, 'file_path'):
                     files.add(file_entry.data_file.file_path)
                 else:
                      logger.warning(f"Could not determine file path for entry in manifest {manifest.manifest_path}")
        return files
    except Exception as e:
        logger.error(f"Error reading manifest list for snapshot {snapshot.snapshot_id}: {e}")
        logger.error(traceback.format_exc()) # Log detailed traceback
        return set() # Return empty set on error

def infer_operation(current_snapshot: Snapshot, previous_snapshot: Snapshot | None, table_io) -> str:
    """Compares data file sets of two snapshots to infer the operation."""
    if previous_snapshot is None:
        return "initial" # First snapshot

    logger.debug(f"Comparing snapshot {current_snapshot.snapshot_id} with previous {previous_snapshot.snapshot_id}")
    current_files = _get_snapshot_data_files(current_snapshot, table_io)
    previous_files = _get_snapshot_data_files(previous_snapshot, table_io)
    logger.debug(f"  Current files ({len(current_files)}): {list(current_files)[:5]}...")
    logger.debug(f"  Previous files ({len(previous_files)}): {list(previous_files)[:5]}...")

    files_added = current_files - previous_files
    files_removed = previous_files - current_files

    logger.debug(f"  Files added: {len(files_added)}, Files removed: {len(files_removed)}")

    if len(files_added) > 0 and len(files_removed) == 0:
        return "append"
    elif len(files_removed) > 0 and len(files_added) == 0:
        # Could be delete, or expire_snapshot (removing old files)
        # Check if summary indicates expire to differentiate? No, summary reading failed.
        return "delete/expire"
    elif len(files_removed) > 0 and len(files_added) > 0:
        return "overwrite/replace"
    elif len(files_added) == 0 and len(files_removed) == 0:
        # Check if parent IDs match - if not, might be fast-forward
        if current_snapshot.parent_snapshot_id == previous_snapshot.snapshot_id:
            return "metadata-update (e.g., schema)" # No file changes, likely schema etc.
        else:
            return "fast-forward / branch-change" # Points to an existing older snapshot
    else:
        return "unknown"


def get_table_history_with_inference(settings):
    """Connects to the Iceberg catalog, loads the table, and prints its history with inferred operations."""

    # --- Configuration from settings --- 
    catalog_name = settings.ICEBERG_DUCKDB_CATALOG_NAME or "r2_catalog_history_script"
    catalog_uri = settings.R2_CATALOG_URI
    catalog_warehouse = settings.R2_CATALOG_WAREHOUSE
    catalog_token = settings.R2_CATALOG_TOKEN
    namespace = settings.ICEBERG_DEFAULT_NAMESPACE
    table_name = settings.ICEBERG_EMAIL_FACTS_TABLE
    full_table_name = f"{namespace}.{table_name}"

    if not all([catalog_uri, catalog_warehouse, catalog_token, namespace, table_name]):
        logger.error("Missing required catalog configuration values in settings.")
        return

    catalog_props = {
        "name": catalog_name,
        "uri": catalog_uri,
        "warehouse": catalog_warehouse,
        "token": catalog_token,
    }
    catalog_props = {k: v for k, v in catalog_props.items() if v is not None}

    _catalog = None
    try:
        logger.info(f"Loading catalog '{catalog_name}' from URI: {catalog_uri}")
        _catalog = load_catalog(**catalog_props)
        logger.info("Catalog loaded successfully.")

        logger.info(f"Loading table: {full_table_name}")
        table: Table = _catalog.load_table(full_table_name)
        logger.info(f"Table '{full_table_name}' loaded.")

        logger.info(f"--- History for {full_table_name} (with inferred operations) ---")
        history = table.history()

        if not history:
            logger.info("No history found for this table.")
            return

        previous_snapshot_id = None
        previous_snapshot: Snapshot | None = None

        for entry in history:
            dt_object = datetime.fromtimestamp(entry.timestamp_ms / 1000)
            inferred_op = "error-loading-snapshot"
            current_snapshot: Snapshot | None = None

            try:
                logger.debug(f"Loading current snapshot: {entry.snapshot_id}")
                current_snapshot = table.snapshot_by_id(entry.snapshot_id)
                if not current_snapshot:
                     logger.warning(f"Failed to load snapshot object for ID {entry.snapshot_id}")
                     raise ValueError(f"Snapshot {entry.snapshot_id} could not be loaded")

                # Load previous snapshot if ID exists
                if previous_snapshot_id:
                     logger.debug(f"Loading previous snapshot: {previous_snapshot_id}")
                     previous_snapshot = table.snapshot_by_id(previous_snapshot_id)
                     if not previous_snapshot:
                         logger.warning(f"Failed to load previous snapshot object for ID {previous_snapshot_id}")
                         # Continue, but inference will be limited
                         previous_snapshot = None 
                else:
                    previous_snapshot = None
                    logger.debug("No previous snapshot ID to load.")

                # Perform inference
                inferred_op = infer_operation(current_snapshot, previous_snapshot, table.io)

            except Exception as load_err:
                logger.error(f"Error processing snapshot {entry.snapshot_id} or its predecessor {previous_snapshot_id}: {load_err}")
                logger.error(traceback.format_exc()) # Log detailed traceback
                # Reset previous snapshot if current fails, to avoid cascading errors
                # previous_snapshot = None 

            print(f"Timestamp: {dt_object.isoformat()}")
            print(f"  Snapshot ID: {entry.snapshot_id}")
            print(f"  Inferred Operation: {inferred_op}")
            # Attempt to print original summary again, even if it failed before
            try:
                original_op = current_snapshot.summary.get('operation', 'unknown') if current_snapshot else 'unknown'
                summary_str = ', '.join(f'{k}={v}' for k, v in current_snapshot.summary.items() if k != 'operation') if current_snapshot else 'Error loading summary'
                print(f"  Original Summary Op: {original_op}")
                print(f"  Original Summary: {{{summary_str}}}")
            except Exception as summary_err:
                 logger.warning(f"  Original Summary Error (Snapshot {entry.snapshot_id}): {summary_err} - likely the tuple error again")
                 print(f"  Original Summary: {{Error loading summary due to: {summary_err}}}")

            print("---")

            # Update previous snapshot for the next iteration
            previous_snapshot_id = entry.snapshot_id
            # Keep the loaded current_snapshot as previous_snapshot for next loop if successful
            # If loading failed, previous_snapshot might be None or the one from the iter before
            # previous_snapshot = current_snapshot # Let's reset previous_snapshot ID instead to be safer


    except NoSuchTableError:
        logger.error(f"Table '{full_table_name}' not found in catalog '{catalog_name}'.")
    except NoSuchNamespaceError:
         logger.error(f"Namespace '{namespace}' not found in catalog '{catalog_name}'.")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        pass

if __name__ == "__main__":
    print("--- Iceberg History Script starting (with inference) ---")
    try:
        # Setup path and load .env
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, '..'))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            logger.info(f"Added project root to sys.path: {project_root}")
        dotenv_path = os.path.join(project_root, '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path)
            logger.info(f"Loaded environment variables from: {dotenv_path}")
        else:
            logger.warning(f".env file not found at: {dotenv_path}.")

        # Import settings
        try:
            from backend.app.config import settings
            logger.info("Successfully imported backend.app.config.settings")
        except ImportError as import_err:
             logger.error(f"Failed to import settings: {import_err}")
             sys.exit(1)

        # Run the history function
        get_table_history_with_inference(settings)

    except Exception as main_err:
        logger.error(f"An error occurred in main execution block: {main_err}", exc_info=True)
    finally:
        print("--- Iceberg History Script finished ---") 