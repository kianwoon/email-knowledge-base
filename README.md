# Email Knowledge Base

[![License: MIT](https://img.shagbadge.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shagbadge.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shagbadge.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shagbadge.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shagbadge.io/badge/React-18+-blue.svg)](https://reactjs.org/)

> An intelligent email knowledge base builder powered by AI, designed to automatically extract, organize, and retrieve insights from your Outlook emails.

## 🌟 Key Features

- **🔗 Microsoft Outlook Integration**: Seamlessly connect to your Outlook account using Microsoft Graph API with OAuth 2.0 authentication
- **🤖 AI-Powered Processing**: Leverage OpenAI GPT models and sentence-transformers for intelligent email analysis and knowledge extraction
- **🔍 Vector-Based Search**: Advanced semantic search using Qdrant vector database for finding relevant information
- **🚀 Async Task Processing**: Efficient background job processing with Celery and Redis
- **🔐 Secure Authentication**: Enterprise-grade security with Azure OAuth and secure token management
- **💾 Knowledge Management**: Organize emails into searchable knowledge bases with automatic categorization
- **📊 Rich Analytics**: Track email processing metrics and knowledge base statistics
- **🎨 Modern UI**: Intuitive React-based frontend with Chakra UI components

## 🏗️ Architecture

### System Overview

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   React Front   │────────▶│   FastAPI       │────────▶│  Microsoft      │
│     end         │  HTTP   │    Backend      │   API   │     Graph API   │
└─────────────────┘         └────────┬────────┘         └─────────────────┘
                                    │
                                    │
                                    ▼
                          ┌─────────────────┐
                          │   Qdrant Vector │
                          │      DB         │
                          └─────────────────┘

                          ┌─────────────────┐
                          │   Celery        │
                          │   + Redis       │
                          └─────────────────┘
```

### Tech Stack

**Frontend:**
- React 18.2 with TypeScript 5.0
- Vite for fast development and building
- Chakra UI for beautiful, accessible components
- Zustand for state management
- React Router for navigation
- Axios for HTTP requests

**Backend:**
- Python 3.10+
- FastAPI 0.104+ for high-performance API
- Uvicorn as ASGI server
- Pydantic for data validation
- Celery 5.3+ for async tasks
- Redis for task queue management

**Integrations:**
- Microsoft Graph API for email access
- MSAL for Azure OAuth authentication
- Qdrant for vector storage and semantic search
- OpenAI API for AI processing
- sentence-transformers for embeddings
- DuckDB and Apache Iceberg for data management

**DevOps:**
- Docker for containerization
- Docker Compose for local development
- pytest for testing
- Black and flake8 for code quality

## 📦 Installation

### Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.10 or higher
- Node.js 18+ and npm
- Docker and Docker Compose (optional, for containerized deployment)
- Microsoft Azure account (for OAuth app registration)
- OpenAI API key (for AI features)

### 1. Clone the Repository

```bash
git clone https://github.com/kianwoon/email-knowledge-base.git
cd email-knowledge-base
```

### 2. Backend Setup

```bash
# Create virtual environment
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration (see Environment Variables section)
```

### 3. Frontend Setup

```bash
cd frontend
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration
```

### 4. Using Docker (Recommended)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## ⚙️ Environment Variables

### Backend (`.env`)

```bash
# Microsoft Azure OAuth Configuration
MS_CLIENT_ID=your-azure-client-id
MS_CLIENT_SECRET=your-azure-client-secret-value
MS_REDIRECT_URI=http://localhost:5173/auth/callback
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000

# Database Configuration
QDRANT_HOST=localhost
QDRANT_PORT=6333
REDIS_URL=redis://localhost:6379/0

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Application Settings
SECRET_KEY=your-secret-key-here
DEBUG=False
LOG_LEVEL=INFO

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### Frontend (`.env.local`)

```bash
VITE_API_BASE_URL=http://localhost:8000/api
VITE_MS_CLIENT_ID=your-azure-client-id
VITE_MS_REDIRECT_URI=http://localhost:5173/auth/callback
```

### Azure OAuth Setup

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Set:
   - Name: `Email Knowledge Base`
   - Supported account types: `Accounts in any organizational directory and personal Microsoft accounts`
   - Redirect URI: `http://localhost:5173/auth/callback`
5. After registration, copy:
   - Application (client) ID → `MS_CLIENT_ID`
   - Directory (tenant) ID → `MS_TENANT_ID`
6. Generate a client secret:
   - Go to **Certificates & secrets** → **New client secret**
   - Copy the **Value** (not the ID) → `MS_CLIENT_SECRET`

## 🚀 Quick Start

### Local Development

1. **Start the Backend:**

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. **Start the Frontend:**

```bash
cd frontend
npm run dev
```

3. **Start Celery Worker (in a new terminal):**

```bash
cd backend
source venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

4. **Start Redis (if not using Docker):**

```bash
redis-server
```

5. **Access the Application:**

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Docker Quick Start

```bash
# Start all services (backend, frontend, redis, qdrant)
docker-compose up -d

# Access the application at http://localhost:5173

# View logs
docker-compose logs -f
```

## 📚 Usage

### 1. Authentication

- Click "Sign in with Microsoft" on the login page
- Authorize the app to access your Outlook emails
- The app will securely store your access token

### 2. Import Emails

- Navigate to the "Import Emails" page
- Select the date range and folders to sync
- Click "Start Import" to begin processing
- Monitor progress in the "Jobs" section

### 3. Search Knowledge Base

- Use the search bar to find relevant information
- Results are ranked by semantic similarity
- Click on results to view original email content

### 4. Manage Knowledge Bases

- Create new knowledge bases for different topics
- Organize emails into categories
- Export knowledge bases as JSON or CSV

## 🔧 API Documentation

Once the backend is running, visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI) or `http://localhost:8000/redoc` for ReDoc documentation.

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Initiate OAuth login |
| `/api/auth/callback` | GET | OAuth callback handler |
| `/api/emails/sync` | POST | Start email sync job |
| `/api/emails/list` | GET | List synced emails |
| `/api/knowledge/search` | POST | Search knowledge base |
| `/api/knowledge/create` | POST | Create new knowledge base |
| `/api/jobs/status/{job_id}` | GET | Get job status |

## 🐳 Deployment

### Using Docker Compose (Production)

1. Update `.env` with production values
2. Set `DEBUG=False` and use strong `SECRET_KEY`
3. Use a proper domain for `FRONTEND_URL` and `BACKEND_URL`
4. Run:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Using Koyeb

The repository includes `.koyeb.yml` for deployment on Koyeb:

```bash
# Install Koyeb CLI
npm install -g @koyeb/cli

# Login and deploy
koyeb login
koyeb app init
```

### Environment-Specific Considerations

**Production:**
- Use HTTPS with proper SSL certificates
- Set strong secrets and rotate them regularly
- Use a managed Redis and Qdrant service
- Configure proper CORS policies
- Enable logging and monitoring
- Set up backups for Qdrant database

**Development:**
- Use `DEBUG=True` for detailed error messages
- Use SQLite or local Qdrant instance
- Configure CORS for frontend development server

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest
pytest --cov=app --cov-report=html
```

### Frontend Tests

```bash
cd frontend
npm test
npm run test:e2e
```

## 🐛 Troubleshooting

### Common Issues

**1. OAuth Redirect Error**
- Ensure `MS_REDIRECT_URI` matches exactly in Azure and `.env`
- Check that Azure app is configured for multi-tenant if needed

**2. Qdrant Connection Failed**
- Verify Qdrant is running: `docker ps` or `ps aux | grep qdrant`
- Check `QDRANT_HOST` and `QDRANT_PORT` in `.env`

**3. Celery Tasks Not Executing**
- Check Redis is running: `redis-cli ping`
- Verify `CELERY_BROKER_URL` matches Redis configuration
- Check Celery worker logs: `docker-compose logs celery`

**4. OpenAI API Rate Limits**
- Implement rate limiting in your application
- Consider using a different model for high-volume processing
- Monitor usage in OpenAI dashboard

### Debug Mode

Enable debug logging by setting:

```bash
# Backend
DEBUG=True
LOG_LEVEL=DEBUG

# Frontend
VITE_DEBUG=true
```

For more detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## 📖 Documentation

- [Architecture Overview](ARCHITECTURE.md) - Detailed system architecture
- [Development Guide](DEVELOPMENT.md) - Setup and contribution guide
- [API Reference](docs/API.md) - Complete API documentation
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use TypeScript strict mode
- Write meaningful commit messages
- Add tests for new features
- Update documentation as needed

## 🗺️ Roadmap

- [ ] Multi-language support for emails
- [ ] Integration with Gmail and other email providers
- [ ] Advanced analytics and reporting
- [ ] Mobile app (React Native)
- [ ] Collaborative knowledge bases
- [ ] Export to various formats (PDF, Markdown, Notion)
- [ ] Email summarization and key insights extraction
- [ ] Integration with other knowledge management tools

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Microsoft Graph API for email integration
- Qdrant team for the vector database
- OpenAI for AI capabilities
- FastAPI and Chakra UI communities for excellent frameworks

## 📞 Support

- 📧 Email: [kianwoon@example.com](mailto:kianwoon@example.com)
- 🐛 Issues: [GitHub Issues](https://github.com/kianwoon/email-knowledge-base/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/kianwoon/email-knowledge-base/discussions)

## 🌐 Links

- [Live Demo](https://email-knowledge-base.vercel.app/) (Coming soon)
- [Documentation](https://docs.email-knowledge-base.com/) (Coming soon)
- [Project Blog](https://blog.email-knowledge-base.com/) (Coming soon)

---

**Built with ❤️ by [Kian Woon](https://github.com/kianwoon)**
