from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime

from app.models.email import EmailReview, EmailApproval, ReviewStatus
from app.models.user import User
from app.routes.auth import get_current_user
from app.services.llm import analyze_email_content

router = APIRouter()

# In-memory storage for email reviews (replace with database in production)
email_reviews = {}


@router.get("/pending", response_model=List[EmailReview])
async def get_pending_reviews(
    department: Optional[str] = None,
    sensitivity: Optional[str] = None,
    is_private: Optional[bool] = None,
    current_user: User = Depends(get_current_user)
):
    """Get list of emails pending review with optional filters"""
    # Filter reviews based on query parameters
    filtered_reviews = [
        review for review in email_reviews.values()
        if review.status == ReviewStatus.PENDING
        and (department is None or review.analysis.department == department)
        and (sensitivity is None or review.analysis.sensitivity == sensitivity)
        and (is_private is None or review.analysis.is_private == is_private)
    ]
    
    return filtered_reviews


@router.get("/{email_id}", response_model=EmailReview)
async def get_review(
    email_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific email review by ID"""
    review = email_reviews.get(email_id)
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
    current_user: User = Depends(get_current_user)
):
    """Approve or reject an email for knowledge base inclusion"""
    review = email_reviews.get(email_id)
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
    email_reviews[email_id] = review
    
    return review


@router.post("/bulk-approve", response_model=List[EmailReview])
async def bulk_approve(
    email_ids: List[str],
    approval: EmailApproval,
    current_user: User = Depends(get_current_user)
):
    """Approve or reject multiple emails at once"""
    updated_reviews = []
    
    for email_id in email_ids:
        review = email_reviews.get(email_id)
        if review:
            # Update review status
            review.status = ReviewStatus.APPROVED if approval.approved else ReviewStatus.REJECTED
            review.reviewed_at = datetime.now()
            review.reviewer_id = current_user.id
            review.review_notes = approval.notes
            
            # Save updated review
            email_reviews[email_id] = review
            updated_reviews.append(review)
    
    return updated_reviews
