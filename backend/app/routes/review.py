import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict
from datetime import datetime, timezone

from app.models.email import EmailReview, EmailApproval, ReviewStatus
from app.models.user import User
from app.dependencies.auth import get_current_active_user
from app.rag.email_rag import analyze_email_content

logger = logging.getLogger("app")
router = APIRouter()

# Placeholder for storing reviews (replace with DB)
email_reviews_store: Dict[str, EmailReview] = {}

@router.get("/pending", response_model=List[EmailReview])
async def get_pending_reviews(
    department: Optional[str] = None,
    sensitivity: Optional[str] = None,
    is_private: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Get list of emails pending review with optional filters"""
    # Filter reviews based on query parameters
    filtered_reviews = [
        review for review in email_reviews_store.values()
        if review.status == ReviewStatus.PENDING
        and (department is None or review.analysis.department == department)
        and (sensitivity is None or review.analysis.sensitivity == sensitivity)
        and (is_private is None or review.analysis.is_private == is_private)
    ]
    
    return filtered_reviews


@router.get("/{email_id}", response_model=EmailReview)
async def get_review(
    email_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific email review by ID"""
    review = email_reviews_store.get(email_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email review not found"
        )
    
    return review


@router.post("/{email_id}/approve", response_model=EmailReview)
async def approve_review(
    email_id: str,
    approval: EmailApproval,
    current_user: User = Depends(get_current_active_user)
):
    """Approve or reject an email for knowledge base inclusion"""
    review = email_reviews_store.get(email_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email review not found"
        )
    
    # Update review status
    review.status = ReviewStatus.APPROVED if approval.approved else ReviewStatus.REJECTED
    review.reviewed_at = datetime.now()
    review.reviewer_id = current_user.id
    review.review_notes = approval.notes
    
    # Save updated review
    email_reviews_store[email_id] = review
    
    return review


@router.post("/bulk-approve", response_model=List[EmailReview])
async def bulk_approve(
    email_ids: List[str],
    approval: EmailApproval,
    current_user: User = Depends(get_current_active_user)
):
    """Approve or reject multiple emails at once"""
    updated_reviews = []
    
    for email_id in email_ids:
        review = email_reviews_store.get(email_id)
        if review:
            # Update review status
            review.status = ReviewStatus.APPROVED if approval.approved else ReviewStatus.REJECTED
            review.reviewed_at = datetime.now()
            review.reviewer_id = current_user.id
            review.review_notes = approval.notes
            
            # Save updated review
            email_reviews_store[email_id] = review
            updated_reviews.append(review)
    
    return updated_reviews

@router.get("/pending", response_model=List[EmailReview])
async def get_pending_reviews_route(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of emails pending review for the current user."""
    logger.info(f"User '{current_user.email}' fetching pending reviews, page: {page}, per_page: {per_page}")
    try:
        # Placeholder logic: Filter in-memory store by owner and pending status
        user_reviews = [r for r in email_reviews_store.values() 
                        if r.reviewer_id == current_user.email and r.status == 'pending'] # Assuming reviewer_id holds owner
        
        # Paginate results (basic example)
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_reviews = user_reviews[start_index:end_index]
        return paginated_reviews
    except Exception as e:
        logger.error(f"Error fetching pending reviews for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to fetch pending reviews."
        )

@router.post("/decision/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
async def submit_review_decision_route(
    email_id: str,
    approval: EmailApproval,
    current_user: User = Depends(get_current_active_user)
):
    """Submit approval/rejection decision for a specific email review."""
    logger.info(f"User '{current_user.email}' submitting review decision for email ID {email_id}: Approved={approval.approved}")
    try:
        # Placeholder logic: Update in-memory store
        if email_id not in email_reviews_store:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
        
        review = email_reviews_store[email_id]
        # Add ownership check if reviewer_id might not be owner
        # if review.owner_id != current_user.email: 
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot review this item.")

        review.status = 'approved' if approval.approved else 'rejected'
        review.review_notes = approval.notes
        review.reviewed_at = datetime.now(timezone.utc)
        review.reviewer_id = current_user.email # Log who reviewed it
        email_reviews_store[email_id] = review # Update the store

        logger.info(f"Review decision for {email_id} submitted successfully.")
        return None # Return None for 204 No Content
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error submitting review decision for email {email_id} by user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to submit review decision."
        )

@router.post("/bulk-decision", status_code=status.HTTP_200_OK) # Or 204 if no body is returned
async def submit_bulk_review_decision_route(
    email_ids: List[str],
    approval: EmailApproval,
    current_user: User = Depends(get_current_active_user)
):
    """Submit bulk approval/rejection decision for multiple email reviews."""
    logger.info(f"User '{current_user.email}' submitting bulk review decision for {len(email_ids)} emails: Approved={approval.approved}")
    if not email_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No email IDs provided for bulk decision.")
    
    processed_count = 0
    failed_ids = []
    new_status = 'approved' if approval.approved else 'rejected'
    
    try:
        for email_id in email_ids:
            if email_id in email_reviews_store:
                review = email_reviews_store[email_id]
                # Add ownership check if needed
                # if review.owner_id == current_user.email:
                review.status = new_status
                review.review_notes = approval.notes # Apply same note to all in bulk
                review.reviewed_at = datetime.now(timezone.utc)
                review.reviewer_id = current_user.email
                email_reviews_store[email_id] = review
                processed_count += 1
                # else: failed_ids.append(email_id) # Permission denied
            else:
                failed_ids.append(email_id) # Not found

        logger.info(f"Bulk decision completed. Processed: {processed_count}, Failed/Skipped: {len(failed_ids)}")
        # Return a summary of results
        return {
            "message": f"Bulk decision submitted.",
            "processed_count": processed_count,
            "failed_ids": failed_ids
        } 
    except Exception as e:
        logger.error(f"Error submitting bulk review decision by user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to submit bulk review decision."
        )

@router.get("/history", response_model=List[EmailReview]) # Adjust response model
async def get_review_history_route(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"), # Filter by status
    current_user: User = Depends(get_current_active_user)
):
    """Get history of email reviews for the current user, with optional filters."""
    logger.info(f"User '{current_user.email}' fetching review history. Filters: status={status_filter}, page={page}, per_page={per_page}")
    try:
        # Placeholder: Filter in-memory store
        user_history = [r for r in email_reviews_store.values() 
                        if r.reviewer_id == current_user.email] # Assuming reviewer is user
        
        if status_filter:
            user_history = [r for r in user_history if r.status == status_filter]
            
        # Paginate results
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        paginated_history = user_history[start_index:end_index]
        return paginated_history
        
    except Exception as e:
        logger.error(f"Error fetching review history for user {current_user.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Failed to fetch review history."
        )