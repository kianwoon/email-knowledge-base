
# 📘 Vector Knowledge Token System – Main App: Step-by-Step Development Plan

## 🔄 Supported & Planned Raw Data Sources

| Source         | Status         | Collection Name Format                                  |
|----------------|----------------|----------------------------------------------------------|
| Email          | ✅ Active       | `kianwoon_wong_int_beyondsoft_com_email_knowledge`      |
| SharePoint     | 🚧 Coming Soon | `kianwoon_wong_int_beyondsoft_com_sharepoint`           |
| Confluence     | 🚧 Coming Soon | `kianwoon_wong_int_beyondsoft_com_confluence`           |
| Elasticsearch  | 🚧 Coming Soon | `kianwoon_wong_int_beyondsoft_com_elasticsearch`        |
| Google Drive   | 🚧 Coming Soon | `kianwoon_wong_int_beyondsoft_com_gdrive`               |
| AWS S3         | 🚧 Coming Soon | `kianwoon_wong_int_beyondsoft_com_s3`                   |

> 🔁 All raw data is processed into the unified vector DB:
> `kianwoon_wong_int_beyondsoft_com_knowledge_base`

---

## 🔸 PHASE 1: Data Architecture Design

### Step 1.1: Setup Qdrant Collections
- Create raw and vector collections as per namespace
- Apply metadata tagging: `source`, `document_type`, `sensitivity_level`

---

## 🔸 PHASE 2: Token Management Backend

### Step 2.1: Token Data Model
- Use UUID, link to owner_id
- Include: sensitivity, allow_list, deny_list, expiry, editable flag

### Step 2.2: Token Endpoints
- `POST /api/token`
- `PATCH /api/token/{id}`
- `DELETE /api/token/{id}`
- `GET /api/token/{id}`
- `POST /api/token/bundle`

---

## 🔸 PHASE 3: Token Validation and Enforcement

### Step 3.1: Access Control Utility
- Validate token rules: allow/deny list, sensitivity rank enforcement

### Step 3.2: Apply on Vector Queries
- Validate result vectors match token rules

---

## 🔸 PHASE 4: Public Vector Access API

### Step 4.1: Endpoint
- `GET /api/shared-knowledge?token=...`
- Middleware applies token logic to filter results

---

## 🔸 PHASE 5: Frontend Token Manager UI

### Step 5.1: Create Token Modal
- Fields: sensitivity, allow list, deny list, expiry
- Save token and show token ID with query endpoint

### Step 5.2: Token Listing & Actions
- List view with edit, revoke, bundle actions

---

## 🔸 PHASE 6: Bundled Token UI

### Step 6.1: Bundle Logic
- Intersection of allow, union of deny
- Highest of sensitivity

---

## 🔸 PHASE 7: Vector Data Summary View

### Step 7.1: Raw Source Breakdown
- Summarize raw sources into visual cards

### Step 7.2: Vector Rollup Display
- Show combined data in “Vector Data” block

---

## 🔸 PHASE 8: Token Export for Middleware

### Step 8.1: Export JSON Structure
- Export token configuration securely
- Optional encryption/signature
