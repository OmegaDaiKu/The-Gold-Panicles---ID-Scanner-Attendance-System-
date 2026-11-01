"""Database schema initialization and auto-migration module."""

from pathlib import Path
from src.database.connection import DatabaseConnectionManager


class SchemaInitializer:
    """Executes DDL statements from schema.sql and handles column migrations for existing databases."""

    def __init__(self, db_manager: DatabaseConnectionManager, sql_path: str = None):
        self.db = db_manager
        if sql_path is None:
            self.sql_path = Path(__file__).parent / "schema.sql"
        else:
            self.sql_path = Path(sql_path)

    def ensure_schema_exists(self) -> None:
        """Reads schema.sql, creates missing tables, and applies schema migrations."""
        if not self.sql_path.exists():
            raise FileNotFoundError(f"Schema SQL script not found at {self.sql_path}")

        with open(self.sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        conn = self.db.get_connection()
        conn.executescript(sql_script)
        self._run_migrations(conn)

    def _run_migrations(self, conn) -> None:
        """Applies schema migrations for legacy database compatibility."""
        cursor = conn.execute("PRAGMA table_info(admin_users);")
        admin_cols = [str(row[1]) for row in cursor.fetchall()]

        if "last_login" not in admin_cols:
            try:
                conn.execute("ALTER TABLE admin_users ADD COLUMN last_login TEXT;")
            except Exception:
                pass

        if "updated_at" not in admin_cols:
            try:
                conn.execute("ALTER TABLE admin_users ADD COLUMN updated_at TEXT;")
            except Exception:
                pass

        cursor = conn.execute("PRAGMA table_info(staff);")
        staff_cols = [str(row[1]) for row in cursor.fetchall()]

        if "designation" not in staff_cols:
            conn.execute("ALTER TABLE staff ADD COLUMN designation TEXT NOT NULL DEFAULT 'Staffer';")