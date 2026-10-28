import sqlite3
import pytest
from src.database.repositories.staff_repo import StaffRepository
from src.core.constants import OFFICIAL_DESIGNATIONS


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE staff (
            staff_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            primary_designation TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE attendance_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(staff_id) REFERENCES staff(staff_id)
        );
    """)
    conn.commit()
    yield conn
    conn.close()


def test_add_staff_valid_designation(db_conn):
    repo = StaffRepository(db_conn)
    valid_designation = OFFICIAL_DESIGNATIONS[0]
    
    assert repo.add_staff("STF-001", "John Doe", valid_designation) is True
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT full_name, primary_designation FROM staff WHERE staff_id = 'STF-001'")
    row = cursor.fetchone()
    assert row == ("John Doe", valid_designation)


def test_add_staff_invalid_designation(db_conn):
    repo = StaffRepository(db_conn)
    with pytest.raises(ValueError, match="Invalid designation"):
        repo.add_staff("STF-002", "Jane Doe", "Unauthorized Role")


def test_delete_staff_without_history_hard_deletes(db_conn):
    repo = StaffRepository(db_conn)
    repo.add_staff("STF-003", "Alice Smith", OFFICIAL_DESIGNATIONS[0])
    
    result = repo.delete_staff("STF-003")
    assert result["status"] == "deleted"
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM staff WHERE staff_id = 'STF-003'")
    assert cursor.fetchone()[0] == 0


def test_delete_staff_with_history_soft_deactivates(db_conn):
    repo = StaffRepository(db_conn)
    repo.add_staff("STF-004", "Bob Jones", OFFICIAL_DESIGNATIONS[1])
    
    # Simulate historical attendance session
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO attendance_sessions (staff_id, status) VALUES ('STF-004', 'CLOSED')")
    db_conn.commit()

    result = repo.delete_staff("STF-004")
    assert result["status"] == "deactivated"

    # Verify row still exists but is_active = 0
    cursor.execute("SELECT is_active FROM staff WHERE staff_id = 'STF-004'")
    assert cursor.fetchone()[0] == 0