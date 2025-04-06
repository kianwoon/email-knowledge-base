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

export interface EmailPreview {
  id: string;
  subject: string;
  sender: string;
  received_date: string;
  snippet: string;
  has_attachments?: boolean;
  importance?: string;
}

export interface EmailFilter {
  folder_id?: string;
  start_date?: string;
  end_date?: string;
  keywords?: string[];
  sender?: string;
  importance?: string;
  has_attachments?: boolean;
  attachment_type?: string;
  advanced_query?: string;
  next_link?: string | undefined;
}

export interface EmailAttachment {
  id: string;
  name: string;
  content_type: string;
  size: number;
  content?: string;
}

export interface EmailContent {
  id: string;
  internet_message_id: string;
  subject: string;
  sender: string;
  sender_email: string;
  recipients: string[];
  cc_recipients?: string[];
  received_date: string;
  body: string;
  is_html: boolean;
  folder_id: string;
  folder_name: string;
  attachments?: EmailAttachment[];
  importance: string;
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

// --- Add Missing Paginated Response Type ---
export interface PaginatedEmailPreviewResponse {
  items: EmailPreview[];
  total: number;
  next_link?: string | null; // Allow null as well as undefined
  current_page: number;
  total_pages: number;
  per_page: number; // Include per_page as returned by backend
}
