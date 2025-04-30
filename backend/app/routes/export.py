# backend/app/routes/export.py
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_active_user, get_validated_token # Added get_validated_token
from app.models.user import User
from app.models.token_models import TokenDB # Import TokenDB
from app.models.export_models import ExportRequest, ExportJobResponse
from app.crud import crud_export_job, token_crud
from app.tasks.export_tasks import export_data_task # Import the Celery task
from app.db.models.export_job import ExportJobStatus # Import the status enum

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/export",
    tags=["Export"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/", 
    response_model=ExportJobResponse, 
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit Data Export Job",
    description="Initiates a background task to export data based on specified parameters and token rules."
)
async def submit_export_job(
    export_request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    # Get the token used for authenticating this API call
    auth_token: TokenDB = Depends(get_validated_token) 
):
    """Submits a data export job to be processed in the background."""
    token_id_to_use: int
    token_to_use: Optional[TokenDB] = None

    try:
        # Determine which token's rules to apply
        if export_request.token_id is not None:
            # User specified a token ID, verify ownership
            token_to_use = token_crud.get_token_by_id(db, token_id=export_request.token_id)
            if not token_to_use or token_to_use.owner_email != current_user.email:
                logger.warning(f"User {current_user.email} requested export with inaccessible token ID {export_request.token_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail=f"Token with ID {export_request.token_id} not found or not owned by user."
                )
            token_id_to_use = export_request.token_id
            logger.info(f"User {current_user.email} initiated export job using specified token ID {token_id_to_use}.")
        else:
            # No token ID specified, use the rules from the authentication token
            token_to_use = auth_token
            token_id_to_use = auth_token.id
            logger.info(f"User {current_user.email} initiated export job using authentication token ID {token_id_to_use}.")

        # TODO: Add validation for export_request.filters based on export_request.source

        # Create the ExportJob record
        new_job = crud_export_job.create_export_job(
            db=db, 
            user_id=current_user.email, 
            token_id=token_id_to_use, 
            export_params=export_request.model_dump(exclude={'token_id'}) # Store source, format, filters
        )

        # Submit the Celery task
        try:
            task = export_data_task.delay(job_id=new_job.id)
            task_id = task.id
            logger.info(f"Submitted export task {task_id} for ExportJob ID {new_job.id}.")

            # Link Celery Task ID back to ExportJob
            updated_job = crud_export_job.update_job_status(
                db=db, 
                job_id=new_job.id, 
                status=new_job.status, # Keep status as PENDING for now
                celery_task_id=task_id
            )
            if not updated_job:
                 logger.error(f"Failed to link Celery task {task_id} to ExportJob {new_job.id}. Job will run but tracking might be inconsistent.")
                 # Decide how critical this is - maybe raise an error or just log

            # Return job info including the task ID
            return ExportJobResponse(
                job_id=new_job.id,
                task_id=task_id,
                status=new_job.status.value # Return the string value of the enum
            )

        except Exception as celery_err:
            logger.error(f"Failed to submit export task to Celery for Job {new_job.id}: {celery_err}", exc_info=True)
            # Mark job as failed before raising HTTP exception
            crud_export_job.update_job_status(
                db=db, 
                job_id=new_job.id, 
                status=ExportJobStatus.FAILED, # Now this should work
                error_message=f"Celery task submission failed: {celery_err}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to submit export job to background processor."
            )

    except HTTPException as http_exc:
        # Re-raise HTTP exceptions (like 404 for token not found)
        raise http_exc
    except Exception as e:
        logger.error(f"Error creating export job for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create export job."
        ) 