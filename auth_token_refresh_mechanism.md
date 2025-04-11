
# Authentication Token Refresh Mechanism

This document outlines the process used in this project to handle the expiration and refresh of Microsoft Graph API access tokens, ensuring a seamless user experience while maintaining security.

## 🎯 Goal
To automatically refresh expired Microsoft access tokens using the stored Microsoft refresh token without requiring the user to manually re-authenticate during an active session, while keeping the refresh logic centralized and service implementations clean.

## 🧩 Key Components

### Internal JWT (`access_token` Cookie)
- A short-lived JSON Web Token stored in an HttpOnly, Secure, SameSite=Lax browser cookie.
- Manages the user's session and contains the current Microsoft Graph access token.

### Microsoft Access Token (in JWT)
- Short-lived (typically 60-90 mins).
- Embedded in the internal JWT for API access (e.g., Outlook, SharePoint).

### Microsoft Refresh Token (in DB)
- Long-lived, issued with `offline_access` scope during login.
- Stored encrypted in the database.
- Used to get new access tokens when the current one expires.

### FastAPI Dependency (`get_current_user`)
- Located at `backend/app/dependencies/auth.py`.
- Validates internal JWT, checks Microsoft token, and triggers refresh if needed.

### Utility Functions (`utils/auth_utils.py`)
- `refresh_ms_token`: Communicates with Microsoft `/token` endpoint, updates DB if needed.
- `create_access_token`: Creates internal JWT with Microsoft access token embedded.

### Services (e.g., `OutlookService`, `SharePointService`)
- Use provided Microsoft access token to call Graph APIs.
- Do not handle refresh logic themselves.

### Database
- Stores the encrypted Microsoft refresh token securely per user.

---

## 🔄 Token Refresh Flow

### 1. API Request
- Frontend calls a protected API (e.g., to get SharePoint data).
- The browser includes the `access_token` JWT cookie.

### 2. Dependency Execution (`get_current_user`)
- Decodes JWT and extracts:
  - Microsoft Graph User ID
  - Email
  - `ms_token`
- Loads user record from DB.

### 3. MS Token Validation
- Calls `/me?$select=id` using `ms_token` to verify token status.

### 4. Handling Validation Results

#### ✅ If Valid (200 OK)
- `ms_token` is used as-is.
- Dependency returns user with token attached.

#### ❌ If Expired (401 Unauthorized)
- `refresh_ms_token(user_id, db)` is called.
  - Retrieves and decrypts refresh token.
  - Requests a new access token.
  - Updates DB if a new refresh token is returned.
- If refresh succeeds:
  - A new JWT is created with `create_access_token`.
  - New cookie is set on response.
  - User object is returned with fresh token.
- If refresh fails:
  - Returns `None`.
  - Raises `HTTPException(401)` → user must re-authenticate.

#### ⚠️ If Other Error
- Logs warning, attempts to proceed with caution.

---

## 🚀 Route Execution
- Route receives a user with a validated (or refreshed) Microsoft token.
- Proceeds to initialize services (e.g., `SharePointService`) with the token.

---

## 📏 Consistency Guidelines for Future Development

### Authentication
- All Graph-auth routes MUST use `Depends(get_current_active_user)`.

### Service Design
- Graph services MUST NOT handle token refresh internally.
- Accept access token on init, bubble up 401 errors.

### Utility Functions
- All auth/token logic belongs in `backend/app/utils/`.

### Token Storage
- Only store Microsoft refresh token in DB.
- Microsoft access token lives inside short-lived internal JWT.

---

## 📁 Relevant File Locations

- `backend/app/dependencies/auth.py` → `get_current_user`, `get_current_active_user`
- `backend/app/utils/auth_utils.py` → `create_access_token`, `refresh_ms_token`
- `backend/app/utils/security.py` → `encrypt_token`, `decrypt_token`
- `backend/app/routes/auth.py` → `/login`, `/callback`, `/logout`, `/me`
- `backend/app/services/outlook.py`, `sharepoint.py` → API service implementations
- `backend/app/crud/user_crud.py` → DB functions for token management
- `backend/app/models/user_models.py` → DB schema, includes `ms_refresh_token` field
