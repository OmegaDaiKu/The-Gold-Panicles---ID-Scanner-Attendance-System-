"""Test suite verifying database connection, schema creation, and PRAGMA execution."""

import os
import tempfile
import sqlite3
import pytest
from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer


@pytest.fixture
def temp_db():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_tgp.db")
    mgr = DatabaseConnectionManager(db_path)
    SchemaInitializer(mgr).ensure_schema_exists()
    yield mgr
    mgr.close()
    temp_dir.cleanup()


def test_database_connection(temp_db):
    """Verifies that the database connects cleanly and PRAGMA table_info executes."""
    conn = temp_db.get_connection()
    assert conn is not None
    cursor = conn.execute("PRAGMA table_info(staff)")
    cols = [str(row[1]) for row in cursor.fetchall()]
    assert "id" in cols or "staff_id" in cols
    assert "name" in cols or "full_name" in cols
