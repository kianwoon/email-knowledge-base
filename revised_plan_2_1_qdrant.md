
# Revised Plan 2.1: User-Specific Collections & `analysis_status` Metadata

---

## 🧠 User-Specific Collection
- The Qdrant collection name will be **derived from the user's email**, e.g.,  
  `kianwoon_wong_int_beyondsoft_com_sharepoint_knowledge`

---

## 🗂️ Qdrant Metadata
- Every vector **must include** the metadata field:  
  ```json
  "analysis_status": "pending"
  ```

---

## 🚀 Phase 1: Persistent Selection (User Collections, `analysis_status`, No UI Status/Deletion)

### ✅ DB Model
- Table: `SharePointSyncItem`
- Fields:
  - `id`
  - `user_id`
  - `item_type`
  - `sharepoint_item_id`
  - `sharepoint_drive_id`
  - `item_name`

> *No status tracking in DB for Phase 1*

---

### 🧩 CRUD Functions
- `add_item`
- `remove_item`
- `get_sync_list_for_user`
- `clear_sync_list_for_user`

---

### 🌐 API Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/sharepoint/sync-list` | Fetch the user's DB list |
| `POST` | `/api/v1/sharepoint/sync-list/add` | Add item/folder to list |
| `DELETE` | `/api/v1/sharepoint/sync-list/remove/{sharepoint_item_id}` | Remove item from list |
| `POST` | `/api/v1/sharepoint/sync-list/process` | Submit Celery task and clear list |

#### `/process` Endpoint Details:
- Gets `user_email` from auth session
- Submits `process_sharepoint_batch_task` with file list + email
- Clears the DB list after task submission
- Returns the `Celery task_id`

---

### 💻 Frontend

- **State Management** for sync list (via API)
- **Checkboxes** in the browse table for add/remove
- `SyncList` component to display current list
- **"Process All"** button:
  - Calls `/process`
  - Shows polling progress for batch task

---

### 🔁 Celery Task: `process_sharepoint_batch_task`

- **Input**: File/folder list + `user_email`
- **Initialize**:
  - Qdrant client
  - SharePointService (with token)
- **Derive Collection Name**:
  - Sanitize email (`.` and `@` → `_`)
  - Append `_sharepoint_knowledge`
- **Ensure Collection Exists**:
  - Check or create collection with dummy vector config (`size=1`, `distance="Cosine"`)
- **Recursive Discovery**:
  - For folders, recursively find child file IDs using SharePointService
- **Processing Loop**:
  - For each file:
    - Update task progress
    - Download content (handle errors)
    - Base64 encode content
    - Prepare metadata (name, type, dates, URLs, etc.)
    - Add `analysis_status = 'pending'` to metadata
    - Generate deterministic point ID (`sharepoint-{item_id}`)
    - Upsert to Qdrant (user-specific collection)

- **Task Completion**:
  - Set final Celery state (`COMPLETED` or `FAILED`)

---

### ✅ Result of Phase 1
- User manages persistent file/folder list
- Processing sends:
  - Base64 content
  - Metadata (including `analysis_status: pending`)
- To a **user-specific Qdrant collection**
- User’s DB list is cleared after processing trigger

---

## 🧩 Phase 2: Add Status Tracking & Qdrant Deletion

### 🛠️ DB Model Enhancements
- Add fields:
  - `status` (Enum)
  - `qdrant_point_id`
  - `error_message`

---

### 🔄 Code/Workflow Enhancements
- Update:
  - CRUD
  - API
  - Celery
  - Frontend

- Track & display status:
  - `'pending'`, `'processing'`, `'processed'`, `'failed'`

---

### 🔁 Trigger Changes
- Replace `/process` with:
  ```
  POST /api/v1/sharepoint/sync-list/process-pending
  ```
  → Only processes `'pending'` items in DB list

---

### 🗑️ Qdrant Deletion Logic
- In `remove_item` CRUD:
  - If item was `'processed'`
  - Use `qdrant_point_id` + user-specific `collection_name`
  - Delete from Qdrant

---

