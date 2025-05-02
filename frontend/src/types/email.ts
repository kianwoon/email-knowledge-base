export enum SensitivityLevel {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  CRITICAL = "critical"
}

export enum Department {
  GENERAL = "general",
  ENGINEERING = "engineering",
  PRODUCT = "product",
  MARKETING = "marketing",
  SALES = "sales",
  FINANCE = "finance",
  HR = "hr",
  LEGAL = "legal",
  OTHER = "other"
}

export enum PIIType {
  NONE = "none",
  NAME = "name",
  EMAIL = "email",
  PHONE = "phone",
  ADDRESS = "address",
  SSN = "ssn",
  PASSPORT = "passport",
  CREDIT_CARD = "credit_card",
  BANK_ACCOUNT = "bank_account",
  DOB = "date_of_birth",
  SALARY = "salary",
  OTHER = "other"
}

export enum ReviewStatus {
  PENDING = "pending",
  APPROVED = "approved",
  REJECTED = "rejected"
}

export interface EmailSender {
  emailAddress: {
    name: string;
    address: string;
  };
}

export interface EmailPreview {
  id: string;
  subject: string | null;
  sender: EmailSender | null;
  receivedDateTime: string | null;
  hasAttachments: boolean;
  importance: 'high' | 'normal' | 'low' | string;
}

export interface EmailFilter {
  folder_id?: string | null;
  keywords?: string[];
  sender?: string;
  recipient?: string;
  start_date?: string;
  end_date?: string;
  has_attachments?: boolean;
  attachment_type?: string;
  importance?: 'high' | 'normal' | 'low';
  advanced_query?: string;
  next_link?: string;
}

export interface EmailAttachment {
  id: string;
  name: string;
  contentType: string;
  size: number;
  isInline: boolean;
}

export interface EmailContent {
  id: string;
  subject: string | null;
  sender: EmailSender | null;
  toRecipients: EmailSender[];
  ccRecipients: EmailSender[];
  bccRecipients: EmailSender[];
  receivedDateTime: string | null;
  sentDateTime: string | null;
  body: EmailBody;
  attachments: EmailAttachment[];
  webLink: string | null;
  importance: 'high' | 'normal' | 'low' | string;
}

export interface EmailAnalysis {
  sensitivity: SensitivityLevel;
  department: Department;
  tags: string[];
  is_private: boolean;
  pii_detected: PIIType[];
  recommended_action: string;
  summary: string;
  key_points: string[];
}

export interface EmailReviewItem {
  email_id: string;
  content: EmailContent;
  analysis: EmailAnalysis;
  status: ReviewStatus;
  reviewed_at?: string;
  reviewer_id?: string;
  review_notes?: string;
}

export interface EmailApproval {
  approved: boolean;
  notes?: string;
}

export interface EmailBody {
  contentType: 'html' | 'text';
  content: string;
}

export interface PaginatedEmailPreviewResponse {
  items: EmailPreview[];
  total: number;
  current_page: number;
  per_page: number;
  total_pages: number;
  next_link?: string | null;
}
