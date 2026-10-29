"""
Utility script to reset any user's password (including the admin account) directly in errorwatch.db.

Usage:
    python reset_password.py
        -> Resets admin@example.com to admin123

    python reset_password.py user@example.com myNewPass123
        -> Resets the specified user's password to the given password
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password

def reset_password(email="admin@example.com", new_password="admin123"):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if not user:
            print(f"Error: User with email '{email}' not found in errorwatch.db.")
            return False

        user.password_hash = hash_password(new_password)
        user.is_active = True
        db.commit()

        print(f"Success! Password for {user.name} ({user.email}) has been reset.")
        print(f"New Password: {new_password}")
        return True
    finally:
        db.close()

if __name__ == "__main__":
    target_email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    target_pass = sys.argv[2] if len(sys.argv) > 2 else "admin123"
    reset_password(target_email, target_pass)
