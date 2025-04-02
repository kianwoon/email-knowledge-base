# Development Guide

## Environment Configuration

### Frontend Configuration
- Frontend URL: `http://localhost:5173`
- Environment files location: `/frontend/.env`
- Key environment variables:
  ```
  VITE_BACKEND_URL=http://127.0.0.1:8000/api
  VITE_API_BASE_URL=http://127.0.0.1:8000/api
  ```

### Backend Configuration
- Backend URL: `http://localhost:8000/api`
- Environment files location: `/backend/.env`
- Key environment variables:
  ```
  DEBUG=True
  JWT_SECRET=development_jwt_secret
  MS_CLIENT_ID=a4b11a39-ee9e-42b6-ab30-788ccef14d89
  MS_TENANT_ID=fda15b03-7d0b-4604-b6a0-00a0712abcf5
  MS_CLIENT_SECRET=[Your Azure Client Secret]
  FRONTEND_URL=http://localhost:5173
  BACKEND_URL=http://localhost:8000/api
  MS_REDIRECT_URI=http://localhost:8000/api/auth/callback
  IS_KOYEB=false
  ```

## Microsoft Azure Configuration
1. App Registration Details:
   - Client ID: `a4b11a39-ee9e-42b6-ab30-788ccef14d89`
   - Tenant ID: `fda15b03-7d0b-4604-b6a0-00a0712abcf5`
   - Redirect URI: `http://localhost:8000/api/auth/callback`

2. Important Notes:
   - Always use the client secret VALUE from Azure Portal, not the secret ID
   - Location: Azure Portal -> App Registrations -> Your App -> Certificates & secrets
   - Under "Client secrets", use the "Value" field, NOT the "Secret ID"

## Running the Application

### Starting the Frontend
```bash
cd frontend
NODE_ENV=development npm run dev
```
- Default port: 5173
- Will automatically try next available port if 5173 is in use

### Starting the Backend
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```
- Default port: 8000
- FastAPI app is mounted with `/api` prefix

## Common Issues and Solutions

### Authentication Issues
1. Invalid Client Secret Error:
   - Error: `AADSTS7000215: Invalid client secret provided`
   - Solution: Make sure to use the actual secret value from Azure Portal, not the secret ID
   - Verify the secret hasn't expired in Azure Portal

2. URL Configuration:
   - Backend URL must include `/api` prefix
   - Redirect URI must match exactly in both Azure Portal and `.env` file
   - Frontend must use the correct backend URL with `/api` prefix

### Port Issues
1. If port 5173 is in use:
   - Frontend will automatically try next available port (5174, 5175, etc.)
   - Update FRONTEND_URL in backend/.env if using different port

2. If port 8000 is in use:
   - Kill existing process: `pkill -f "uvicorn app.main:app"`
   - Or use a different port and update all configurations accordingly

## Debugging Tips
1. Check environment variables in logs:
   ```
   DEBUG - FRONTEND_URL: http://localhost:5173
   DEBUG - BACKEND_URL: http://localhost:8000/api
   DEBUG - MS_REDIRECT_URI: http://localhost:8000/api/auth/callback
   ```

2. Monitor authentication flow:
   - Login request logs
   - Callback request logs
   - Token exchange logs

3. Verify URL consistency:
   - Azure Portal redirect URI
   - Frontend API base URL
   - Backend URL configuration
   - MS_REDIRECT_URI in backend/.env 