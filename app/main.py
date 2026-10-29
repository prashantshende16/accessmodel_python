import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.security import hash_password
from .db.session import engine, SessionLocal
from .models import (
    Base, User, Organization, OrganizationMembership,
    Project, ProjectCredential, Issue, ErrorEvent,
    UptimeCheck, UptimeResult, Incident, AlertRule, AlertDelivery
)
from .api.v1.auth import router as auth_router
from .api.v1.organizations import router as org_router
from .api.v1.projects import router as project_router
from .api.v1.events import router as event_router
from .api.v1.issues import router as issue_router
from .api.v1.uptime import router as uptime_router
from .api.v1.alerts import router as alert_router
from .api.v1.dashboard import router as dashboard_router

# Initialize tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Universal Application Error Monitoring Platform Backend",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API V1
api_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_prefix)
app.include_router(org_router, prefix=api_prefix)
app.include_router(project_router, prefix=api_prefix)
app.include_router(event_router, prefix=api_prefix)
app.include_router(issue_router, prefix=api_prefix)
app.include_router(uptime_router, prefix=api_prefix)
app.include_router(alert_router, prefix=api_prefix)
app.include_router(dashboard_router, prefix=api_prefix)

@app.get("/healthz")
def health_check():
    return {"status": "ok", "platform": "ErrorWatch", "timestamp": datetime.datetime.utcnow()}

def seed_demo_data():
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            # 1. Admin user
            admin = User(
                name="Admin Engineer",
                email="admin@example.com",
                password_hash=hash_password("admin123"),
                is_active=True,
            )
            db.add(admin)
            db.flush()

            # 2. Organization
            org = Organization(name="Acme Engineering", slug="acme-engineering")
            db.add(org)
            db.flush()

            membership = OrganizationMembership(
                user_id=admin.id,
                organization_id=org.id,
                role="Owner"
            )
            db.add(membership)

            # 3. Two sample projects: React Storefront and FastAPI Backend
            react_proj = Project(
                organization_id=org.id,
                name="React Web Storefront",
                slug="react-web-storefront",
                platform="react",
                environment="production",
                description="Public customer-facing web application",
                status="connected",
                last_event_at=datetime.datetime.utcnow(),
            )
            db.add(react_proj)
            db.flush()

            react_cred = ProjectCredential(
                project_id=react_proj.id,
                client_key="ew_client_react_demo_key_998877",
                secret_key="ew_sec_react_demo_secret_112233"
            )
            db.add(react_cred)

            py_proj = Project(
                organization_id=org.id,
                name="Core API Service",
                slug="core-api-service",
                platform="fastapi",
                environment="production",
                description="FastAPI REST services for order processing & auth",
                status="connected",
                last_event_at=datetime.datetime.utcnow(),
            )
            db.add(py_proj)
            db.flush()

            py_cred = ProjectCredential(
                project_id=py_proj.id,
                client_key="ew_client_fastapi_demo_key_445566",
                secret_key="ew_sec_fastapi_demo_secret_778899"
            )
            db.add(py_cred)

            # 4. Seed initial Issues and ErrorEvents
            react_issue = Issue(
                project_id=react_proj.id,
                fingerprint="fp_react_typeerror_cart_checkout",
                title="TypeError: Cannot read properties of undefined (reading 'items')",
                exception_type="TypeError",
                message="Cannot read properties of undefined (reading 'items') at calculateTotal",
                environment="production",
                severity="critical",
                status="unresolved",
                event_count=14,
                user_count=8,
                first_seen=datetime.datetime.utcnow() - datetime.timedelta(hours=6),
                last_seen=datetime.datetime.utcnow(),
            )
            db.add(react_issue)
            db.flush()

            react_event = ErrorEvent(
                issue_id=react_issue.id,
                project_id=react_proj.id,
                environment="production",
                release="2.4.1",
                exception_type="TypeError",
                message="Cannot read properties of undefined (reading 'items') at calculateTotal",
                stacktrace=[
                    {"filename": "src/components/Checkout.jsx", "function": "calculateTotal", "lineno": 98, "colno": 21, "in_app": True, "code": "const total = cart.items.reduce((acc, i) => acc + i.price, 0);"},
                    {"filename": "src/pages/CartPage.jsx", "function": "CartPage", "lineno": 54, "colno": 12, "in_app": True, "code": "<Checkout cart={data.cart} onPay={handlePay} />"},
                    {"filename": "node_modules/react-dom/cjs/react-dom.production.min.js", "function": "renderWithHooks", "lineno": 14938, "colno": 18, "in_app": False, "code": "null"},
                ],
                request_context={"method": "POST", "url": "https://store.example.com/checkout", "headers": {"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}},
                user_context={"id": "usr_948", "email": "customer@buyer.com"},
                breadcrumbs=[
                    {"category": "navigation", "message": "User navigated to /cart", "level": "info"},
                    {"category": "ui.click", "message": "Clicked 'Proceed to Checkout' button", "level": "info"},
                    {"category": "xhr", "message": "POST /api/v1/cart returned 200", "level": "info"},
                ],
                tags={"browser": "Chrome 128.0", "os": "macOS", "viewport": "1440x900"},
            )
            db.add(react_event)

            py_issue = Issue(
                project_id=py_proj.id,
                fingerprint="fp_fastapi_database_timeout",
                title="OperationalError: database connection timeout after 5000ms",
                exception_type="OperationalError",
                message="psycopg2.OperationalError: server closed the connection unexpectedly",
                environment="production",
                severity="error",
                status="unresolved",
                event_count=5,
                user_count=3,
                first_seen=datetime.datetime.utcnow() - datetime.timedelta(hours=2),
                last_seen=datetime.datetime.utcnow(),
            )
            db.add(py_issue)
            db.flush()

            py_event = ErrorEvent(
                issue_id=py_issue.id,
                project_id=py_proj.id,
                environment="production",
                release="1.18.0",
                exception_type="OperationalError",
                message="psycopg2.OperationalError: server closed the connection unexpectedly",
                stacktrace=[
                    {"filename": "app/db/connection.py", "function": "get_connection", "lineno": 44, "in_app": True, "code": "conn = pool.getconn(timeout=5)"},
                    {"filename": "app/services/orders.py", "function": "create_order", "lineno": 112, "in_app": True, "code": "with get_connection() as conn:"},
                    {"filename": "app/api/v1/orders.py", "function": "place_order", "lineno": 65, "in_app": True, "code": "order = order_service.create_order(payload)"},
                ],
                request_context={"method": "POST", "url": "https://api.example.com/api/v1/orders", "headers": {"user-agent": "Axios/1.7.2"}},
                user_context={"id": "cust_33", "email": "shopper@store.com"},
                breadcrumbs=[
                    {"category": "auth", "message": "JWT Bearer token authenticated for user 33", "level": "info"},
                    {"category": "log", "message": "Inventory reserved for SKU #8812", "level": "info"},
                ],
                tags={"runtime": "Python 3.10", "framework": "FastAPI", "worker_id": "uvicorn-worker-3"},
            )
            db.add(py_event)

            # 5. Uptime check & alert rule
            uptime_check = UptimeCheck(
                project_id=py_proj.id,
                name="Core API Health Endpoint",
                url="https://httpbin.org/status/200",
                method="GET",
                interval_seconds=60,
                expected_status=200,
                status="up",
                last_check_at=datetime.datetime.utcnow(),
                last_latency_ms=124.5,
                uptime_percentage=99.98,
            )
            db.add(uptime_check)
            db.flush()

            check_result = UptimeResult(
                check_id=uptime_check.id,
                status_code=200,
                latency_ms=124.5,
                is_success=True,
                error_message="",
                checked_at=datetime.datetime.utcnow(),
            )
            db.add(check_result)

            alert_rule = AlertRule(
                project_id=react_proj.id,
                name="Production Critical Errors Alert",
                trigger_type="new_issue",
                channel="in_app",
                destination="dev-team@acme.com",
            )
            db.add(alert_rule)
            db.flush()

            delivery = AlertDelivery(
                rule_id=alert_rule.id,
                title="New Issue: TypeError in React Web Storefront",
                message="A new critical issue occurred in production: Cannot read properties of undefined (reading 'items')",
                status="delivered",
                payload={"issue_id": react_issue.id}
            )
            db.add(delivery)

            db.commit()
    finally:
        db.close()

# Seed demo data on startup
seed_demo_data()
