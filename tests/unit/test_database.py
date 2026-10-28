"""Unit tests verifying SQLite schema creation, foreign keys, and repository DAOs."""

import sqlite3
import pytest

from src.core.constants import OFFICIAL_DESIGNATIONS
from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer
from src.database.repositories.staff_repo import StaffRepository
from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.visitor_repo import VisitorRepository


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh temporary SQLite DatabaseConnectionManager instance."""
    db_file = tmp_path / "test_tgp.db"
    db_manager = DatabaseConnectionManager(str(db_file))
    schema = SchemaInitializer(db_manager)
    schema.ensure_schema_exists()
    yield db_manager
    db_manager.close()


def test_schema_and_official_designations(temp_db):
    """Verifies that the schema initializes cleanly and accepts official designations."""
    assert len(OFFICIAL_DESIGNATIONS) == 22

    staff_repo = StaffRepository(temp_db)
    sid = staff_repo.create("261-00105", "Jules Leo Reserva", designation="Editor-in-Chief", created_at="2026-10-16T12:00:00Z")
    assert sid > 0

    record = staff_repo.get_by_id(sid)
    assert record["full_name"] == "Jules Leo Reserva"
    assert record["designation"] == "Editor-in-Chief"


def test_unique_open_session_guardrail(temp_db):
    """Verifies that SQLite partial index prevents duplicate OPEN sessions for the same staffer."""
    staff_repo = StaffRepository(temp_db)
    att_repo = AttendanceRepository(temp_db)

    sid = staff_repo.create("261-00105", "Jules Leo Reserva", designation="Editor-in-Chief", created_at="2026-10-16T12:00:00Z")
    
    # 1. Create First Open Session
    att_repo.create_session(sid, category="Duty", time_in="2026-10-16T12:00:00Z")

    # 2. Attempt Second Open Session for same staffer -> Must raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        att_repo.create_session(sid, category="Visit", time_in="2026-10-16T12:05:00Z")


def test_independent_timestamps_staff_lifecycle(temp_db):
    """Verifies that time_in and time_out are stored independently."""
    staff_repo = StaffRepository(temp_db)
    att_repo = AttendanceRepository(temp_db)

    sid = staff_repo.create("261-00105", "Jules Leo Reserva", designation="Editor-in-Chief", created_at="2026-10-16T12:00:00Z")
    session_id = att_repo.create_session(sid, category="Duty", time_in="2026-10-16T12:00:00Z")

    open_session = att_repo.get_by_id(session_id)
    assert open_session["time_in"] == "2026-10-16T12:00:00Z"
    assert open_session["time_out"] is None
    assert open_session["status"] == "OPEN"

    # Close Session
    closed = att_repo.close_session(session_id, time_out="2026-10-16T16:00:00Z")
    assert closed is True

    completed = att_repo.get_by_id(session_id)
    assert completed["time_in"] == "2026-10-16T12:00:00Z"
    assert completed["time_out"] == "2026-10-16T16:00:00Z"
    assert completed["status"] == "COMPLETED"


def test_visitor_visits_lifecycle(temp_db):
    """Verifies guest visitor check-in and check-out with separate timestamp storage."""
    vis_repo = VisitorRepository(temp_db)

    visit_id = vis_repo.create_visit("261-99812", "Guest Student", time_in="2026-10-16T13:00:00Z")
    assert visit_id > 0

    open_visit = vis_repo.get_open_visit_by_student_id("261-99812")
    assert open_visit["visitor_name"] == "Guest Student"
    assert open_visit["time_out"] is None

    closed = vis_repo.close_visit(visit_id, time_out="2026-10-16T14:30:00Z")
    assert closed is True

    updated = vis_repo.get_by_id(visit_id)
    assert updated["time_out"] == "2026-10-16T14:30:00Z"
    assert updated["status"] == "COMPLETED"