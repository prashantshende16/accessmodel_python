"""
Utility script to reset any user's password (including the admin account) directly in app.db.

Usage:
    python reset_password.py
        -> Resets admin@example.com to admin123

    python reset_password.py user@example.com myNewPass123
        -> Resets the specified user's password to the given password
"""
import sys
import os

# Import password hashing and db connection from main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import connect, hash_password

def reset_password(email="admin@example.com", new_password="admin123"):
    conn = connect()
    user = conn.execute(
        "SELECT id, name, email, role FROM users WHERE lower(email) = lower(?)",
        (email.strip(),),
    ).fetchone()

    if not user:
        print(f"Error: User with email '{email}' not found in app.db.")
        conn.close()
        return False

    new_hash = hash_password(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ?, is_active = 1 WHERE id = ?",
        (new_hash, user["id"]),
    )
    conn.commit()
    conn.close()

    print(f"Success! Password for {user['name']} ({user['email']}) has been reset.")
    print(f"New Password: {new_password}")
    return True

if __name__ == "__main__":
    target_email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    target_pass = sys.argv[2] if len(sys.argv) > 2 else "admin123"
    reset_password(target_email, target_pass)

