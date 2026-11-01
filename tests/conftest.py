import pytest

from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer


@pytest.fixture
def db_manager(tmp_path):
    """Give each test an isolated SQLite database with the real application schema."""
    db_path = tmp_path / "test_attendance.db"
    manager = DatabaseConnectionManager(str(db_path))
    SchemaInitializer(manager).ensure_schema_exists()

    try:
        yield manager
    finally:
        manager.close()


@pytest.fixture
def sample_staff(db_manager):
    """Insert a staff row using the production schema, returning its integer PK."""
    with db_manager.transaction() as conn:
        cursor = conn.execute(
            """
            INSERT INTO staff
                (student_id_no, full_name, designation, is_active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            ("261-00105", "Test Staff Member", "News Writer", "2026-01-01T00:00:00+00:00"),
        )
        return cursor.lastrowid
