# RBAC Backend (FastAPI + SQLite)

Role-Based Access Control backend application with SQLite storage and JWT authentication.

## Features
- Granular per-user, per-page permissions (`view`, `add`, `edit`, `delete`).
- Auto-creating SQLite database (`app.db`) on first startup.
- Password hashing using PBKDF2 HMAC SHA-256.
- Password reset utility script: `python reset_password.py`.

## Setup & Run

```bash
python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API documentation available at `http://127.0.0.1:8000/docs`.

### Default Credentials
- **Admin**: `admin@example.com` / `admin123`
- **User**: `user@example.com` / `user123`
