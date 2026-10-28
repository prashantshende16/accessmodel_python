"""
RBAC backend: FastAPI + SQLite (single file DB, no extra database server needed).

Run:  uvicorn main:app --reload --port 8000
Default logins (created on first start):
    admin@example.com / admin123   (role: admin  -> full access to everything)
    user@example.com  / user123    (role: user   -> only what admin grants)
"""
import datetime
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import List, Optional

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-before-production-use-1234567890")
TOKEN_HOURS = 12

# The "pages" that can be permission-controlled. Keep in sync with frontend/src/config.js
PAGES = [
    {"key": "products", "name": "Products"},
    {"key": "orders", "name": "Orders"},
    {"key": "customers", "name": "Customers"},
    {"key": "reports", "name": "Reports"},
]
PAGE_KEYS = {p["key"] for p in PAGES}
ACTIONS = ("view", "add", "edit", "delete")

app = FastAPI(title="RBAC API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------- database
def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return hmac.compare_digest(check, digest)


def init_db():
    conn = connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin','user')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS permissions (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            page_key TEXT NOT NULL,
            can_view INTEGER NOT NULL DEFAULT 0,
            can_add INTEGER NOT NULL DEFAULT 0,
            can_edit INTEGER NOT NULL DEFAULT 0,
            can_delete INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, page_key)
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
            ("Administrator", "admin@example.com", hash_password("admin123"), "admin"),
        )
        cur = conn.execute(
            "INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)",
            ("Demo User", "user@example.com", hash_password("user123"), "user"),
        )
        uid = cur.lastrowid
        # demo user: products view+add+edit, orders view only
        conn.execute("INSERT INTO permissions VALUES (?,?,?,?,?,?)", (uid, "products", 1, 1, 1, 0))
        conn.execute("INSERT INTO permissions VALUES (?,?,?,?,?,?)", (uid, "orders", 1, 0, 0, 0))
        samples = [
            ("products", "Laptop", "14 inch business laptop", "active"),
            ("products", "Mouse", "Wireless mouse", "active"),
            ("orders", "Order #1001", "2 x Laptop", "pending"),
            ("orders", "Order #1002", "5 x Mouse", "active"),
            ("customers", "Acme Pvt Ltd", "Pune", "active"),
            ("reports", "Monthly Sales", "October summary", "active"),
        ]
        conn.executemany("INSERT INTO records (page_key,title,description,status) VALUES (?,?,?,?)", samples)
    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()


# --------------------------------------------------------------------- auth
def make_token(user) -> str:
    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def current_user(authorization: Optional[str] = Header(None), db=Depends(get_db)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    token = authorization.split(" ", 1)[1]
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = db.execute("SELECT * FROM users WHERE id = ?", (int(data["sub"]),)).fetchone()
    if not user or not user["is_active"]:
        raise HTTPException(401, "User not found or disabled")
    return user


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    return user


def permissions_for(db, user) -> dict:
    """Return {page_key: {view,add,edit,delete}}. Admin gets everything."""
    if user["role"] == "admin":
        return {p["key"]: {a: True for a in ACTIONS} for p in PAGES}
    result = {p["key"]: {a: False for a in ACTIONS} for p in PAGES}
    rows = db.execute("SELECT * FROM permissions WHERE user_id = ?", (user["id"],)).fetchall()
    for r in rows:
        if r["page_key"] in result:
            result[r["page_key"]] = {
                "view": bool(r["can_view"]),
                "add": bool(r["can_add"]),
                "edit": bool(r["can_edit"]),
                "delete": bool(r["can_delete"]),
            }
    return result


def check_perm(db, user, page_key: str, action: str):
    if page_key not in PAGE_KEYS:
        raise HTTPException(404, "Unknown page")
    if not permissions_for(db, user)[page_key][action]:
        raise HTTPException(403, f"You do not have '{action}' permission on {page_key}")


def public_user(u) -> dict:
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"], "is_active": bool(u["is_active"])}


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn, db=Depends(get_db)):
    email_clean = body.email.strip().lower()
    pwd = body.password
    print(f"[LOGIN ATTEMPT] email='{email_clean}', pwd_len={len(pwd)}, pwd_repr={repr(pwd)}")
    user = db.execute(
        "SELECT * FROM users WHERE lower(email) = ? OR (lower(email) = lower(?) || '@example.com')",
        (email_clean, email_clean),
    ).fetchone()
    if not user:
        print(f"[LOGIN FAIL] User not found for email: '{email_clean}'")
        raise HTTPException(401, "Wrong email or password")
    if not (verify_password(pwd, user["password_hash"]) or verify_password(pwd.strip(), user["password_hash"])):
        print(f"[LOGIN FAIL] Password mismatch for user '{email_clean}'")
        raise HTTPException(401, "Wrong email or password")
    if not user["is_active"]:
        raise HTTPException(403, "Your account is disabled. Contact admin.")
    return {"token": make_token(user), "user": public_user(user), "permissions": permissions_for(db, user)}


@app.get("/api/auth/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    return {"user": public_user(user), "permissions": permissions_for(db, user)}


@app.get("/api/pages")
def list_pages(user=Depends(current_user)):
    return PAGES


# ----------------------------------------------------------- user management
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "user"
    is_active: bool = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


def validate_role(role: str):
    if role not in ("admin", "user"):
        raise HTTPException(400, "Role must be 'admin' or 'user'")


@app.get("/api/users")
def list_users(_=Depends(require_admin), db=Depends(get_db)):
    rows = db.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [public_user(r) for r in rows]


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, _=Depends(require_admin), db=Depends(get_db)):
    validate_role(body.role)
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    try:
        cur = db.execute(
            "INSERT INTO users (name,email,password_hash,role,is_active) VALUES (?,?,?,?,?)",
            (body.name.strip(), body.email.strip().lower(), hash_password(body.password), body.role, int(body.is_active)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already exists")
    return public_user(db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.put("/api/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, admin=Depends(require_admin), db=Depends(get_db)):
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        raise HTTPException(404, "User not found")
    if body.role is not None:
        validate_role(body.role)
    if user_id == admin["id"] and (body.role == "user" or body.is_active is False):
        raise HTTPException(400, "You cannot demote or disable your own account")
    fields = {
        "name": body.name.strip() if body.name else target["name"],
        "email": body.email.strip().lower() if body.email else target["email"],
        "role": body.role or target["role"],
        "is_active": int(body.is_active) if body.is_active is not None else target["is_active"],
        "password_hash": hash_password(body.password) if body.password else target["password_hash"],
    }
    if body.password and len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    try:
        db.execute(
            "UPDATE users SET name=?, email=?, role=?, is_active=?, password_hash=? WHERE id=?",
            (fields["name"], fields["email"], fields["role"], fields["is_active"], fields["password_hash"], user_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already exists")
    return public_user(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, admin=Depends(require_admin), db=Depends(get_db)):
    if user_id == admin["id"]:
        raise HTTPException(400, "You cannot delete your own account")
    cur = db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "User not found")
    return {"ok": True}


# ------------------------------------------------------ permission management
class PermItem(BaseModel):
    page_key: str
    can_view: bool = False
    can_add: bool = False
    can_edit: bool = False
    can_delete: bool = False


class PermIn(BaseModel):
    permissions: List[PermItem]


@app.get("/api/users/{user_id}/permissions")
def get_user_permissions(user_id: int, _=Depends(require_admin), db=Depends(get_db)):
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        raise HTTPException(404, "User not found")
    return {"user": public_user(target), "pages": PAGES, "permissions": permissions_for(db, target)}


@app.put("/api/users/{user_id}/permissions")
def set_user_permissions(user_id: int, body: PermIn, _=Depends(require_admin), db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
        raise HTTPException(404, "User not found")
    for item in body.permissions:
        if item.page_key not in PAGE_KEYS:
            raise HTTPException(400, f"Unknown page '{item.page_key}'")
        # add/edit/delete are useless without view, so they imply view
        can_view = item.can_view or item.can_add or item.can_edit or item.can_delete
        db.execute(
            "INSERT OR REPLACE INTO permissions (user_id,page_key,can_view,can_add,can_edit,can_delete) VALUES (?,?,?,?,?,?)",
            (user_id, item.page_key, int(can_view), int(item.can_add), int(item.can_edit), int(item.can_delete)),
        )
    db.commit()
    target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return {"permissions": permissions_for(db, target)}


# ------------------------------------------------------------------ dashboard
@app.get("/api/dashboard")
def dashboard(user=Depends(current_user), db=Depends(get_db)):
    perms = permissions_for(db, user)
    cards = []
    for p in PAGES:
        if perms[p["key"]]["view"]:
            count = db.execute("SELECT COUNT(*) FROM records WHERE page_key = ?", (p["key"],)).fetchone()[0]
            cards.append({"key": p["key"], "name": p["name"], "count": count})
    data = {"cards": cards}
    if user["role"] == "admin":
        data["total_users"] = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        data["active_users"] = db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
    return data


# ------------------------------------------------- sample pages: generic CRUD
class RecordIn(BaseModel):
    title: str
    description: str = ""
    status: str = "active"


@app.get("/api/records/{page_key}")
def list_records(page_key: str, user=Depends(current_user), db=Depends(get_db)):
    check_perm(db, user, page_key, "view")
    rows = db.execute("SELECT * FROM records WHERE page_key = ? ORDER BY id DESC", (page_key,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/records/{page_key}", status_code=201)
def create_record(page_key: str, body: RecordIn, user=Depends(current_user), db=Depends(get_db)):
    check_perm(db, user, page_key, "add")
    cur = db.execute(
        "INSERT INTO records (page_key,title,description,status,created_by) VALUES (?,?,?,?,?)",
        (page_key, body.title.strip(), body.description, body.status, user["id"]),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM records WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.put("/api/records/{page_key}/{record_id}")
def update_record(page_key: str, record_id: int, body: RecordIn, user=Depends(current_user), db=Depends(get_db)):
    check_perm(db, user, page_key, "edit")
    cur = db.execute(
        "UPDATE records SET title=?, description=?, status=? WHERE id=? AND page_key=?",
        (body.title.strip(), body.description, body.status, record_id, page_key),
    )
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Record not found")
    return dict(db.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone())


@app.delete("/api/records/{page_key}/{record_id}")
def delete_record(page_key: str, record_id: int, user=Depends(current_user), db=Depends(get_db)):
    check_perm(db, user, page_key, "delete")
    cur = db.execute("DELETE FROM records WHERE id=? AND page_key=?", (record_id, page_key))
    db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Record not found")
    return {"ok": True}
