# Koyeb Deployment Notes

## Latest Deployment Changes
- Date: April 2024
- Changes: Updated service configuration for Microsoft authentication
- Components Updated:
  - Frontend service
    - Updated API base URL to use /api prefix
    - Changed port to 3000
    - Updated nginx configuration for client-side routing
  - Backend service
    - Added Microsoft OAuth environment variables
    - Updated routes to use /api prefix
    - Changed port to 8000

## Configuration Details
- Frontend URL: https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app
- Backend API URL: https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api
- Auth Callback URL: https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api/auth/callback

## Environment Variables
### Frontend
- VITE_API_BASE_URL: https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api

### Backend
- MS_CLIENT_ID: a4b11a39-ee9e-42b6-ab30-788ccef14d89
- MS_TENANT_ID: fda15b03-7d0b-4604-b6a0-00a0712abcf5
- FRONTEND_URL: https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app
- BACKEND_URL: https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api

## Required Manual Steps
1. Update Azure App Registration redirect URIs:
   - Add: https://email-knowledge-base-2-automationtesting-ba741710.koyeb.app/api/auth/callback
2. Set sensitive environment variables in Koyeb:
   - MS_CLIENT_SECRET
   - JWT_SECRET
