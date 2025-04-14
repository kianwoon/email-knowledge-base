# Azure Blob Storage Integration Plan

## Benefits of Storing Configuration

- Users can manage multiple Azure Blob Storage connections.
- The backend can retrieve credentials (e.g., connection strings, account names, or SAS tokens) when needed.
- Associated settings like sync preferences per connection can be stored.

---

## Revised Plan

### Backend (`backend/app/`)

#### Dependencies
- Add `azure-storage-blob` to `requirements.txt`.

#### Configuration
- Decide on the initial authentication method (User Identity, Connection String, SAS, SP?).
- Define necessary base environment variables (`.env.example`).

#### Database

**New Table:** `azure_blob_connections`

| Column         | Description |
|----------------|-------------|
| id             | Primary Key |
| user_id        | Foreign Key (references `users.id`) |
| name           | User-defined name (e.g., "Work Storage") |
| account_name   | Azure Storage account name |
| auth_type      | Enum/String (e.g., 'connection_string', 'sas_token', 'user_ms_identity') |
| credentials    | Encrypted field for sensitive data |
| container_name | (Optional) Default or primary container |
| is_active      | Boolean |
| created_at     | Timestamp |
| updated_at     | Timestamp |

**Optional Table:** `azure_blob_sync_jobs` if complex sync logic is needed.

#### Migrations
- Create and apply Alembic migrations for new table(s).

### Models & Schemas (`models/`, `schemas/`)

- **SQLAlchemy model**: `AzureBlobConnection`
- **Pydantic schemas**: 
  - `AzureBlobConnectionCreate`
  - `AzureBlobConnectionUpdate`
  - `AzureBlobConnectionRead`

### CRUD (`crud/`)

- File: `crud_azure_blob.py`
- Implement:
  - `create_connection`
  - `get_connection`
  - `get_connections_by_user`
  - `update_connection`
  - `delete_connection`
- **Note**: Ensure encryption/decryption for `credentials` field.

### Services (`services/`)

- File: `azure_blob_service.py`
- Class: `AzureBlobService`

**Initialization:**
- Accept `AzureBlobConnection` object or its details.
- Initialize `BlobServiceClient` using `azure-storage-blob` SDK based on `auth_type`.

**Core Logic:**
- Implement methods for list/upload/download/etc.

**Guidelines:**
- Do not handle token refresh; use provided credentials.
- Propagate exceptions.

### Routes (`routes/`)

- File: `azure_blob.py`

**Endpoints:**
- `/azure_blob/connections`: `POST` (create), `GET` (list)
- `/azure_blob/connections/{connection_id}`: `GET`, `PUT/PATCH`, `DELETE`
- `/azure_blob/connections/{connection_id}/containers`: `GET`
- `/azure_blob/connections/{connection_id}/blobs`: `GET`, `POST`

**Authentication:**
- Use `Depends(get_current_active_user)`
- Validate ownership via `current_user.id`
- Fetch connection via CRUD and pass to `AzureBlobService`

### Celery Tasks (`tasks/`)

- File: `azure_blob_tasks.py` (if needed)
- Task:
  - Accepts `user_id`, `connection_id`
  - Fetch connection, decrypt credentials
  - Use `AzureBlobService` to run logic

---

## Frontend (`frontend/src/`)

### API Client
- Add support for `/azure_blob/connections/...` endpoints.

### Pages/Components
- Manage connections (create/view/edit/delete)
- Select active connection
- Browse containers/blobs
- Handle uploads

### State Management
- Store:
  - List of connections
  - Selected connection details
  - Blob lists, etc.

### Routing/UI
- Add navigation and error handling.
- Use backend authentication.

---

## Testing

- Update tests for:
  - CRUD operations
  - Connection management
  - Service logic with various auth types