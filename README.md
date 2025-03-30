# Outlook Email Knowledge Base Builder

A secure application that connects to Microsoft Outlook, analyzes emails using AI, and builds a searchable knowledge base from approved content.

## Features

- **Outlook Integration**: Secure OAuth2 authentication with Microsoft Graph API
- **Email Filtering**: Select folders, date ranges, and keywords to narrow down analysis
- **Content Extraction**: Parse emails and attachments (PDF, DOCX, etc.)
- **AI-Powered Analysis**: Automatically tag and classify emails using ChatGPT-4o mini
- **PII Detection**: Identify and flag sensitive personal information
- **Review Workflow**: Approve or reject content before adding to knowledge base
- **Vector Database**: Store embedded knowledge in Qdrant for semantic search
- **Search Interface**: Find relevant information using natural language queries
- **Audit Logging**: Track all actions for compliance and governance

## Tech Stack

- **Backend**: FastAPI (Python 3.11.6)
- **Frontend**: React + Chakra UI
- **LLM**: OpenAI ChatGPT-4o mini
- **Embeddings**: OpenAI text-embedding-3-small
- **Vector DB**: Qdrant
- **Authentication**: OAuth2 with Microsoft Identity

## Getting Started

### Prerequisites

- Python 3.11.6
- Node.js 18+
- Microsoft Azure account (for app registration)
- OpenAI API key
- Qdrant instance (local or cloud)

### Setup

1. Clone the repository
2. Create and configure `.env` file (see `.env.example`)
3. Install backend dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   ```
4. Install frontend dependencies:
   ```
   cd frontend
   npm install
   ```

### Running the Application

1. Start the backend:
   ```
   cd backend
   uvicorn app.main:app --reload
   ```
2. Start the frontend:
   ```
   cd frontend
   npm run dev
   ```
3. Open your browser at http://localhost:3000

## Development Workflow

See [architecture.md](./docs/architecture.md) for detailed information about the system design and components.

## Mobile Responsiveness
The application is fully responsive and optimized for mobile devices, with special attention to navigation elements and layout adjustments.

## License

MIT
