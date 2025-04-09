
# ✅ Step-by-Step Plan: Async Email to Knowledge Base with Celery, Redis, PostgreSQL & Progress Tracking

> This plan outlines the end-to-end conversion of the synchronous process to an asynchronous, fault-tolerant, and traceable task system using Celery + Redis, with full token management and frontend feedback.

---

## 🧱 Phase 0: Setup & Prerequisites (Updated)

| Step | Task | Status |
|------|------|--------|
| 0.1 | Install Redis | ✅ DONE |
| 0.2 | Update `.env` with `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` | ✅ DONE |
| 0.3 | Add `celery[redis]>=5.3.6` and `redis>=5.0.0` to `requirements.txt` and install | ✅ DONE |

---

### 🔐 Step 0.4: Secure Refresh Token Storage (PostgreSQL)

| Sub-Step | Task | Status |
|----------|------|--------|
| 0.4.1 | Add `ENCRYPTION_KEY` to `.env` and `Settings` class (`app/config.py`) | 🟡 MODIFY |
|        | Example:  
```env
ENCRYPTION_KEY=your-generated-key-here
```  
Load in `Settings`:  
```python
ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")
```  
Generate using Python:  
```python
from cryptography.fernet import Fernet  
Fernet.generate_key().decode()
```  
⚠️ **Do NOT commit this key** — store securely in production (e.g., AWS Secrets Manager, Vault, etc.).

---

### 💾 Token Storage Model

| Sub-Step | Task | Status |
|----------|------|--------|
| 0.4.2 | In `backend/app/db/models/user.py`, define token field | 🟡 MODIFY |
- **Option A (Manual Encryption)**:  
  ```python
  ms_refresh_token = Column(LargeBinary, nullable=True)
  ```
- **Option B (SQLAlchemy-Utils - Recommended)**:  
  Install and import:
  ```bash
  pip install sqlalchemy-utils
  ```
  Then:
  ```python
  from sqlalchemy_utils import EncryptedType
  from cryptography.fernet import Fernet
  from app.core.config import settings

  ms_refresh_token = Column(EncryptedType(String, settings.ENCRYPTION_KEY), nullable=True)
  ```

---

### 🔐 Option A: Manual Encryption

| Sub-Step | Task | Status |
|----------|------|--------|
| A.1 | Create `encrypt_token(token, key)` and `decrypt_token(encrypted_token, key)` using `cryptography.fernet.Fernet` | 🆕 |
| A.2 | In `auth.py`, call `encrypt_token(...)` before saving token to DB | 🆕 |
| A.3 | In `tasks.py`, call `decrypt_token(...)` before using the token in MSAL | 🆕 |

```python
# utils/security.py
from cryptography.fernet import Fernet

def encrypt_token(token: str, key: str) -> bytes:
    return Fernet(key.encode()).encrypt(token.encode())

def decrypt_token(token: bytes, key: str) -> str:
    return Fernet(key.encode()).decrypt(token).decode()
```

---

### ✅ Option B: SQLAlchemy-Utils (Recommended)

| Sub-Step | Task | Status |
|----------|------|--------|
| B.1 | Install `sqlalchemy-utils` and use `EncryptedType` in the User model | ✅ RECOMMENDED |
| B.2 | SQLAlchemy will handle encryption/decryption automatically | ✅ SIMPLIFIES LOGIC |
| B.3 | In `auth.py`, save the token directly:  
```python
user.ms_refresh_token = refresh_token
```  
| B.4 | In `tasks.py`, retrieve with:  
```python
refresh_token = user.ms_refresh_token  # Already decrypted
```  

---

### ✅ Final Verification

| Step | Task | Status |
|------|------|--------|
| 0.4.3 | Confirm the OAuth callback in `auth.py` saves the refresh token correctly | 🟡 VERIFY |
| 0.4.4 | Confirm the Celery task (`tasks.py`) retrieves and uses the decrypted token | 🟡 VERIFY |
