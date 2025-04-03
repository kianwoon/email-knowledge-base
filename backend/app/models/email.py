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
    has_attachments: bool = False
    importance: str = "normal"


class EmailFilter(BaseModel):
    folder_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    keywords: Optional[List[str]] = None
    sender: Optional[str] = None


class EmailAttachment(BaseModel):
    """Model for email attachments"""
    id: str
    name: str
    content_type: str
    size: int
    content: Optional[str] = None


class EmailContent(BaseModel):
    """Model for full email content"""
    id: str
    subject: str
    sender: str
    received_date: str
    body: str
    attachments: Optional[List[EmailAttachment]] = []


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
