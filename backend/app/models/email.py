from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SensitivityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Department(str, Enum):
    GENERAL = "general"
    ENGINEERING = "engineering"
    PRODUCT = "product"
    MARKETING = "marketing"
    SALES = "sales"
    FINANCE = "finance"
    HR = "hr"
    LEGAL = "legal"
    OTHER = "other"


class PIIType(str, Enum):
    NONE = "none"
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    SSN = "ssn"
    PASSPORT = "passport"
    CREDIT_CARD = "credit_card"
    BANK_ACCOUNT = "bank_account"
    DOB = "date_of_birth"
    SALARY = "salary"
    OTHER = "other"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EmailPreview(BaseModel):
    """Model for email preview data"""
    id: str
    subject: str
    sender: str
    received_date: str
    snippet: str  # This field stores the preview/summary of the email body
    importance: str = "normal"
    has_attachments: bool = False


class PaginatedEmailPreviewResponse(BaseModel):
    """Model for paginated list of email previews."""
    items: List[Dict[str, Any]] = Field(default_factory=list, description="List of email previews (raw dicts from Graph API)")
    total: Optional[int] = Field(None, description="Total count of items if available (often not provided by Graph API list calls)")
    next_link: Optional[str] = Field(None, description="URL to fetch the next page of results from MS Graph API")

    model_config = {
        "extra": "ignore" # Ignore extra fields from Graph API if any
    }


class EmailFilter(BaseModel):
    folder_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    keywords: Optional[List[str]] = None
    sender: Optional[str] = None
    next_link: Optional[str] = None  # For pagination using Microsoft Graph API's nextLink


class EmailAttachment(BaseModel):
    """Model for email attachments"""
    id: str
    name: str
    content_type: Optional[str]
    size: int
    content: Optional[str] = None


class EmailContent(BaseModel):
    """Model for full email content"""
    id: str
    internet_message_id: Optional[str] = None
    subject: str
    sender: str
    sender_email: Optional[str] = None
    recipients: Optional[List[str]] = None
    cc_recipients: Optional[List[str]] = None
    received_date: Optional[str]
    sent_date: Optional[datetime] = None
    body: str
    is_html: bool = False
    folder_id: Optional[str] = None
    folder_name: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = Field(default_factory=list)
    importance: Optional[str] = None


class EmailAnalysis(BaseModel):
    sensitivity: SensitivityLevel = Field(..., description="How sensitive is this information")
    department: Department = Field(..., description="Which department this knowledge belongs to")
    tags: List[str] = Field(..., description="Relevant tags for categorizing this content")
    is_private: bool = Field(..., description="Whether this contains private/confidential information")
    pii_detected: List[PIIType] = Field(default_factory=list, description="Types of personal identifiable information detected")
    recommended_action: str = Field(..., description="Recommended action (store/exclude)")
    summary: str = Field(..., description="Brief summary of the content")
    key_points: List[str] = Field(..., description="Key knowledge points extracted")


class EmailReview(BaseModel):
    email_id: str
    content: EmailContent
    analysis: EmailAnalysis
    status: ReviewStatus = ReviewStatus.PENDING
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[str] = None
    review_notes: Optional[str] = None


class EmailApproval(BaseModel):
    approved: bool
    notes: Optional[str] = None


class EmailVectorData(BaseModel):
    id: str
    email_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime = Field(default_factory=datetime.now)


class EmailUpdateRequest(BaseModel):
    """Model for updating specific fields of an email record (e.g., status, tags)."""
    status: Optional[ReviewStatus] = None
    tags: Optional[List[str]] = None
    # Add other fields that might need updating
    review_notes: Optional[str] = None


class EmailAnalysisJob(BaseModel):
    job_id: str
    status: str
    owner: str
    filter_criteria: EmailFilter
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# Added to resolve import error in routes/email.py
class PreviewResponse(BaseModel):
    """Response model for email previews (potentially non-paginated or legacy)."""
    items: List[EmailPreview] = Field(default_factory=list)
    # Add other fields if necessary based on usage, e.g., total count
    # total: Optional[int] = None


# Added to resolve import error in routes/email.py
# Potentially redundant with EmailPreview, added for compatibility
class PreviewEmail(BaseModel):
    """Model for email preview data (potentially legacy or alternative)."""
    id: str
    subject: str
    sender: str
    received_date: str
    snippet: str
    importance: str = "normal"
    has_attachments: bool = False
