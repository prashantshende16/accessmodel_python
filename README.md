# ErrorWatch Backend (Python + FastAPI + SQLAlchemy)

Universal Application Error Monitoring Platform Backend service.

## Core Capabilities
- **Event Ingestion Engine (`POST /api/v1/events`)**: High-throughput public ingestion endpoint accepting exceptions, stack traces, breadcrumbs, and request context from SDKs.
- **Deterministic Issue Grouping**: Groups duplicate events into stable issues by hashing exception type and normalized in-app stack frames (does not group by dynamic messages alone).
- **Data Redaction & Scrubbing**: Automatically scrubs sensitive headers and parameters (passwords, tokens, authorization secrets).
- **Multi-tenant Organization & Project Isolation**: Each project is assigned a public client ingestion key (`ew_client_...`).
- **Independent Uptime Monitoring**: Probes external endpoints with latency measurement, failure streaks, and incident creation.
- **Alert Dispatch Engine**: Configurable alert triggers for new issues, error spikes, and service outages with delivery audit logs.

## Setup & Run

```bash
cd backend
python -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Database (`errorwatch.db`) and demo data are initialized automatically on startup.

API Documentation: `http://127.0.0.1:8000/docs`

### Default Demo Credentials
- **Admin**: `admin@example.com` / `admin123`
- Emergency password reset: `python reset_password.py [email] [new_pass]`
