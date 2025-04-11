
# Development Guidelines: Adding New Features, Pages, or Functions

## 🔐 New Backend Routes Requiring Authentication

### Dependency Usage
- Any new FastAPI route in `backend/app/routes/` that requires authentication **MUST** use the primary authentication dependency:
  ```python
  @router.get("/new-protected-feature")
  async def new_protected_feature(current_user: User = Depends(get_current_active_user)):
      ...
  ```

### Token Access
- `current_user.ms_access_token`:
  - If the user is authenticated via web session (cookie): contains the valid (or refreshed) Microsoft Graph access token.
  - If authenticated via API key: will be `None`.

### Graph API Calls
- Always check if `ms_access_token` exists before making Microsoft Graph API calls or passing the token to a service:
  ```python
  if current_user.ms_access_token:
      # Proceed with Graph API call
  ```

---

## 🛠️ New Backend Services Interacting with Microsoft Graph

### Initialization
- Any new service class (e.g., in `backend/app/services/`) calling Graph APIs **MUST** accept the access token during initialization:
  ```python
  class TeamsService:
      def __init__(self, ms_token: str):
          self.ms_token = ms_token
  ```

### No Refresh Logic
- These services **MUST NOT** perform any token refresh or validation internally.
- Rely on the route/dependency to provide a valid access token.

### Error Propagation
- Let exceptions (e.g., `response.raise_for_status()` from `httpx`) bubble up to the caller or FastAPI error handler.

---

## 📦 New Celery Tasks Interacting with Microsoft Graph

### Task Dispatch
- When dispatching a task from a route, **pass the user’s identifier** (e.g., `current_user.email`), **not** the access token.

### Task Logic
Inside the task function:
1. Open a new DB session.
2. Fetch the user with `get_user_with_refresh_token`.
3. Decrypt the stored Microsoft refresh token using `decrypt_token`.
4. Use MSAL to get a fresh access token:
   ```python
   msal_app.acquire_token_by_refresh_token(...)
   ```
5. Use the fresh token for Microsoft Graph calls.
6. Handle errors gracefully (e.g., refresh token missing or revoked).

---

## 🌐 New Frontend Pages/Components

### API Calls
- Use backend endpoints protected by:
  ```python
  Depends(get_current_active_user_or_token_owner)
  ```

### Error Handling
- Ensure your frontend HTTP client (e.g., `apiClient.ts`) has global error interceptors:
  - Catch `401 Unauthorized` responses.
  - Redirect the user to login if session is invalid or refresh fails.

### No Refresh Logic in Frontend
- The frontend does **not** handle token refresh directly — this is done transparently by the backend.

---

## 🧱 Utilities and Models

- Add authentication and security helpers to:
  ```text
  backend/app/utils/
  ```

- Add database interaction logic for users/tokens to:
  ```text
  backend/app/crud/
  ```

- Add Pydantic or SQLAlchemy models to:
  ```text
  backend/app/models/ or backend/app/schemas/
  ```
