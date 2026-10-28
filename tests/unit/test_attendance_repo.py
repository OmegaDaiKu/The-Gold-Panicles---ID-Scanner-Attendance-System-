import sqlite3
import pytest
from src.database.repositories.attendance_repo import AttendanceRepository


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE attendance_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            time_in TEXT NOT NULL,
            status TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE visitor_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name TEXT NOT NULL,
            time_in TEXT NOT NULL,
            status TEXT NOT NULL
        );
    """)
    conn.commit()
    yield conn
    conn.close()


def test_dashboard_metrics(db_conn):
    cursor = db_conn.cursor()
    
    # Active staff in office
    cursor.execute("INSERT INTO attendance_sessions (staff_id, time_in, status) VALUES ('S1', datetime('now'), 'OPEN')")
    cursor.execute("INSERT INTO attendance_sessions (staff_id, time_in, status) VALUES ('S2', datetime('now'), 'OPEN')")
    
    # Overdue staff session
    cursor.execute("INSERT INTO attendance_sessions (staff_id, time_in, status) VALUES ('S3', datetime('now', '-9 hours'), 'OVERDUE')")
    
    # Active visitors
    cursor.execute("INSERT INTO visitor_visits (visitor_name, time_in, status) VALUES ('Guest A', datetime('now'), 'OPEN')")

    db_conn.commit()

    repo = AttendanceRepository(db_conn)
    metrics = repo.get_dashboard_metrics()

    assert metrics["staff_in_office"] == 2
    assert metrics["active_visitors"] == 1
    assert metrics["overdue_sessions"] == 1
    assert metrics["total_entries_today"] == 4


def test_attendance_repo_crud_methods(db_conn):
    """Verifies get_recent_sessions, update_session, and delete_session."""
    repo = AttendanceRepository(db_conn)

    sid = repo.create_session("S10", "Duty", time_in="2026-10-17T08:00:00Z")
    assert sid > 0

    recent = repo.get_recent_sessions(limit=10)
    assert len(recent) > 0
    assert any(r["id"] == sid for r in recent)

    # Test update
    updated = repo.update_session(sid, status="COMPLETED")
    assert updated is True

    record = repo.get_by_id(sid)
    assert record["status"] == "COMPLETED"

    # Test delete
    deleted = repo.delete_session(sid)
    assert deleted is True
    assert repo.get_by_id(sid) is None