# ✅ Finalized Step-by-Step App Development Plan (with Chakra UI)

---

## 🔧 STEP 0 – Setup & Environment

| Task                                  | Tools / Notes                                                |
|---------------------------------------|--------------------------------------------------------------|
| Create monorepo or two separate apps  | `/backend` (FastAPI), `/frontend` (React + Chakra UI)       |
| Choose LLM provider(s)                | ChatGPT-4o mini (economical choice for tagging)             |
| Choose Vector DB                      | Qdrant (recommended for flexibility and metadata support)   |
| Python version               | 3.11.6 |
| Create `.env` structure               | Store API keys, secrets, model configs                      |
---

## 🔐 STEP 1 – Outlook Integration & Auth Flow

| Task                                       | Notes                                                              |
|--------------------------------------------|--------------------------------------------------------------------|
| Implement OAuth2 using Microsoft Identity  | Authorization Code Flow                                            |
| Request scopes                             | `Mail.Read`, `Mail.ReadWrite`, `offline_access`                   |
| Securely store access/refresh tokens       | Needed for long-lived mailbox access                               |
| Add Microsoft Graph API integration        | `/me/messages`, `/me/mailFolders` for emails + folders             |

📌 **Outcome**: User can sign in and grant access to their Outlook mailbox.

---

## 🔍 STEP 2 – Email Filtering + Preview Interface

| Task                              | Description                                                    |
|-----------------------------------|----------------------------------------------------------------|
| UI for filters                    | Folder selection, date range, keyword filters (Chakra Forms)   |
| API: `POST /email/preview`       | Returns sample: subject, sender, snippet                      |
| API: `GET /email/folders`        | Returns Outlook folder list                                   |
| Preview limit                     | 5–10 emails for performance                                    |

📌 **Outcome**: User previews matching emails before committing analysis.

---

## 📥 STEP 3 – Email Fetching + Content Extraction

| Task                                 | Notes                                                           |
|--------------------------------------|-----------------------------------------------------------------|
| Fetch full email content             | Use MS Graph `/messages/{id}`                                   |
| Extract + parse attachments          | Use `pdfminer`, `python-docx`, `openpyxl`, etc.                |
| Deduplicate messages                 | Use `internetMessageId` or `messageId`                         |
| Structure payload for LLM            | Email + attachment content for classification                  |

📌 **Outcome**: Email data prepared for LLM analysis.

---

## 🤖 STEP 4 – LLM-Based Tagging & PII Detection

| Task                                   | Description                                                             |
|----------------------------------------|-------------------------------------------------------------------------|
| Build prompt for ChatGPT-4o mini       | Output: sensitivity, department, tags, private data types               |
| LLM returns structured JSON            | Including `is_private`, `recommended_action`, and label color           |
| Detect personal data                   | (salary, passport, bank account, etc.)                                  |
| Store analysis result                  | Email status = `Pending`, stored for review                             |

📌 **Outcome**: Emails classified and labeled, flagged if private.

---

## 📋 STEP 5 – Review Interface (Approval Workflow)

| Task                                 | Description                                                           |
|--------------------------------------|-----------------------------------------------------------------------|
| Chakra UI for data review UI         | Use `Badge`, `Tag`, `Accordion`, `Table`, `Drawer`                   |
| List pending emails                  | Show title, tags, PII flags, recommended action                      |
| Filters                              | Sensitivity, department, tag type (private/knowledge)                |
| Approve / Reject controls            | Per email and in bulk                                                |
| APIs: `GET /emails/pending`, `POST /emails/:id/approve` | Review workflow                   |

📌 **Outcome**: User selects what gets exported into the knowledge base.

---

## 🔄 STEP 6 – Embedding + Export to Vector DB

| Task                                 | Description                                                     |
|--------------------------------------|-----------------------------------------------------------------|
| Use embedding model                  | `text-embedding-3-small` (OpenAI)                               |
| Embed approved knowledge             | Combine `title + content` into vector                           |
| Store in Qdrant                      | With metadata (sensitivity, department, owner, etc.)            |
| Track source email                   | Store message ID for traceability                               |

📌 **Outcome**: Only approved knowledge is embedded and stored.

---

## 🔍 STEP 7 – (Optional) Search & Query Interface

| Task                                 | Description                                                     |
|--------------------------------------|-----------------------------------------------------------------|
| Chakra UI for query page             | Use `Input`, `Select`, `List`, `Tooltip`, `Popover`, etc.       |
| Semantic + keyword search            | Search across embedded knowledge base                           |
| Filters                              | Sensitivity, department, date, category                         |
| Result metadata                      | Title, tags, match score                                        |

📌 **Outcome**: Users can retrieve embedded knowledge via semantic search.

---

## 🧾 STEP 8 – Audit Logging & Data Compliance

| Task                                 | Description                                                    |
|--------------------------------------|----------------------------------------------------------------|
| Log all user actions                 | Approve/reject decisions, LLM classifications                  |
| Flag personal data                   | Store types flagged, reason for exclusion                      |
| Retention control                    | Set auto-delete or manual cleanup rules                        |

📌 **Outcome**: Compliant, traceable system with full audit history.

---

## 🚀 Deployment & DevOps

| Area               | Tool / Platform                            |
|--------------------|---------------------------------------------|
| Dev Platform       | Cursor / Windsurf                           |
| Vector DB          | Qdrant Cloud                                |
| Backend hosting    | Render / Railway / Fly.io                   |
| Frontend           | Vite + React + Chakra UI                    |
| CI/CD              | GitHub Actions or Windsurf built-in tools   |

---

## ✅ Suggested Kickoff Order

| Order | Step                                 | Notes                                      |
|-------|--------------------------------------|--------------------------------------------|
| 1     | Step 0 + Step 1                      | Environment and OAuth setup                 |
| 2     | Step 2 (Filter + Preview)            | Preview logic + early UI with Chakra        |
| 3     | Step 3–4 (LLM pipeline)              | Core analysis flow                          |
| 4     | Step 5 (Review UI)                   | Chakra-based tagging + approval UX          |
| 5     | Step 6 (Vector Export)               | Embedding pipeline                          |
| 6     | Step 7–8 (Search + Audit)            | Full user control & governance              |

---

# 📁 Project File Structure

my-email-knowledge-app/
│
├── .env                      # Environment variables (backend keys, tokens)
├── .gitignore
├── README.md
├── requirements.txt          # Python dependencies (for FastAPI backend)
├── package.json              # Node dependencies (for frontend)
├── docker-compose.yml        # Optional Docker container setup
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI entrypoint
│   │   ├── config.py                   # Env & app settings
│   │   ├── models/                     # Pydantic + ORM models
│   │   │   ├── email.py                # Email structure, tagging, etc.
│   │   │   └── user.py
│   │   ├── routes/                     # FastAPI route handlers
│   │   │   ├── auth.py                 # Outlook OAuth
│   │   │   ├── email.py                # Preview, fetch, analyze
│   │   │   ├── review.py               # Approve / reject APIs
│   │   │   └── vector.py               # Embedding + export
│   │   ├── services/                   # Logic layer
│   │   │   ├── outlook.py              # MS Graph integration
│   │   │   ├── parser.py               # Attachment parsing (PDF, DOCX, etc.)
│   │   │   ├── llm.py                  # LLM tagging and PII detection
│   │   │   ├── embedder.py             # Embedding functions
│   │   │   └── audit.py                # Action logging
│   │   ├── db/                         # DB access and models
│   │   │   └── session.py              # DB session init
│   │   └── utils/                      # Shared utilities (e.g., deduplication)
│   │       └── logger.py
│   └── tests/                          # Backend test suite
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                        # Axios or fetch wrappers
│   │   │   └── email.ts
│   │   ├── components/
│   │   │   ├── EmailPreview.tsx
│   │   │   ├── EmailReviewTable.tsx
│   │   │   ├── TagBadge.tsx
│   │   │   └── FilterControls.tsx
│   │   ├── pages/
│   │   │   ├── SignIn.tsx
│   │   │   ├── FilterSetup.tsx
│   │   │   ├── EmailReview.tsx
│   │   │   └── Search.tsx
│   │   ├── context/                    # App-wide state management
│   │   └── styles/                     # Tailwind or CSS modules
│   └── tailwind.config.js
│
└── docs/
    ├── architecture.md                 # Diagrams and explanation
    ├── prompts/                        # LLM prompt templates
    │   ├── classify-email.md
    │   └── pii-detection.md
    ├── api-spec.md                     # REST API contract
    └── vector-db-schema.md            # Metadata used for vector search
