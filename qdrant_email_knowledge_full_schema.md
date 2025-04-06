# 📄 Qdrant Collection Documentation: `email_knowledge` (Multi-Document Type)

## Overview
The `email_knowledge` collection stores different types of knowledge base entries resulting from user-triggered analysis jobs. Each job is identified by a shared `job_id` and includes:
- The filtered emails (`type: email`)
- The query criteria used (`type: query_criteria`)
- The subject analysis results (`type: analysis_chart`)

---

## 🗂️ Collection Name
```
email_knowledge
```

---

## 📐 Vector Configuration
| Property   | Value            |
|------------|------------------|
| `size`     | 1536 (e.g., OpenAI embedding) |
| `distance` | `Cosine`         |

---

## 🧩 Metadata Schema

### Common Fields

| Field     | Type     | Description |
|-----------|----------|-------------|
| `type`     | `string` | Document type: `"email"`, `"query_criteria"`, or `"analysis_chart"` |
| `job_id`   | `string` | Shared UUID for linking all entries in a single job |
| `owner`    | `string` | Email address of the Outlook-authenticated user |

---

### 📧 Email Entry (`type: email`)

| Field             | Type        | Description |
|------------------|-------------|-------------|
| `sender`          | `string`    | Sender's email address |
| `subject`         | `string`    | Subject line |
| `date`            | `string`    | ISO format (`YYYY-MM-DD`) |
| `has_attachments` | `boolean`   | True if attachments exist |
| `folder`          | `string`    | Folder name (Inbox, Sent, etc.) |
| `tags`            | `string[]`  | Subject-level tags |
| `analysis_status` | `string`    | NLP processing status |
| `status`          | `string`    | Business status (e.g. reviewed, archived) |
| `source`          | `string`    | Always `"email"` |
| `raw_text`        | `string`    | Body of the email |
| `attachments`     | `array`     | List of base64-encoded attachments |
| `attachment_count`| `integer`   | Number of attachments |

#### Attachments Subfields

| Field           | Type     | Description |
|-----------------|----------|-------------|
| `filename`       | `string` | File name |
| `mimetype`       | `string` | MIME type |
| `size`           | `integer`| Size in bytes |
| `content_base64` | `string` | Base64-encoded binary content |

---

### 🔍 Query Criteria Entry (`type: query_criteria`)

| Field             | Type     | Description |
|------------------|----------|-------------|
| `query_criteria`  | `object` | Original filter used in the UI |

#### Subfields of `query_criteria`

| Field        | Type       | Description |
|--------------|------------|-------------|
| `folder`      | `string`   | Filtered folder |
| `from_date`   | `string`   | Start date (`YYYY-MM-DD`) |
| `to_date`     | `string`   | End date (`YYYY-MM-DD`) |
| `keywords`    | `string[]` | User-provided keywords |

---

### 📊 Analysis Chart Entry (`type: analysis_chart`)

| Field         | Type      | Description |
|---------------|-----------|-------------|
| `status`       | `string`  | Chart generation status |
| `chart_data`   | `array`   | List of classified tag results |

#### Subfields of `chart_data[]`

| Field     | Type     | Description |
|-----------|----------|-------------|
| `tag`      | `string` | Assigned tag |
| `cluster`  | `string` | Higher-level category |
| `subject`  | `string` | Original email subject |

---

## 🧪 Sample Email Entry

```json
{
  "type": "email",
  "job_id": "job-1234",
  "owner": "user@company.com",
  "sender": "john@example.com",
  "subject": "Request for Assistance",
  "date": "2025-04-04",
  "has_attachments": true,
  "folder": "Inbox",
  "tags": ["staffing"],
  "analysis_status": "completed",
  "status": "reviewed",
  "source": "email",
  "raw_text": "Please see attached...",
  "attachments": [
    {
      "filename": "request.pdf",
      "mimetype": "application/pdf",
      "size": 84212,
      "content_base64": "JVBERi0xLjQK..."
    }
  ],
  "attachment_count": 1
}
```

---

## 🛡️ Best Practices

- All entries are linked by `job_id`
- Use `type` for clean filtering across mixed-purpose collection
- Ensure `attachment_count` is accurate for email integrity checks
- Avoid large base64 blobs unless under 5MB per file
- Index on `owner`, `job_id`, and `type` for efficient filtering

