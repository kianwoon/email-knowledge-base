# Email Knowledge Base Builder

A full-stack application that integrates with Microsoft Graph API to build a knowledge base from your email communications.

## Features
- Microsoft OAuth Authentication
- Email folder and message retrieval
- Modern UI with Vite + React + TypeScript
- FastAPI backend with Microsoft Graph API integration

## Setup

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

## Environment Variables
Create `.env` files in both frontend and backend directories with the following variables:

Frontend:
```
VITE_MICROSOFT_CLIENT_ID=your_client_id
VITE_API_BASE_URL=http://localhost:8000
```

Backend:
```
MICROSOFT_CLIENT_ID=your_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret
MICROSOFT_REDIRECT_URI=http://localhost:5173/auth/callback
```

## Tech Stack
- Frontend: React, TypeScript, Vite, Chakra UI
- Backend: FastAPI, Python, Microsoft Graph API

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

## License 1.0

MIT
