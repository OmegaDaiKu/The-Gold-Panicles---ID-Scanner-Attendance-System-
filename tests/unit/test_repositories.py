"""Test suite verifying repository CRUD operations with PRAGMA column parsing."""

import os
import tempfile
import pytest
from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer
from src.database.repositories.staff_repo import StaffRepository
from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.admin_repo import AdminRepository
from src.services.auth_service import AuthService


@pytest.fixture
def temp_db():
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_repo.db")
    mgr = DatabaseConnectionManager(db_path)
    SchemaInitializer(mgr).ensure_schema_exists()
    yield mgr
    mgr.close()
    temp_dir.cleanup()


def test_staff_repo_crud(temp_db):
    staff_repo = StaffRepository(temp_db)
    # Create staff member
    staff_id = staff_repo.create(
        staff_id="2026-00001",
        full_name="Jane Doe",
        designation="News Writer",
    )
    assert staff_id > 0

    # Retrieve staff
    staff = staff_repo.get_by_id(staff_id)
    assert staff is not None
    assert staff["student_id_no"] == "2026-00001"
    assert staff["full_name"] == "Jane Doe"

    # Fetch by student_id
    by_sid = staff_repo.get_by_student_id("2026-00001")
    assert by_sid is not None
    assert by_sid["id"] == staff_id


def test_attendance_repo_crud(temp_db):
    staff_repo = StaffRepository(temp_db)
    staff_id = staff_repo.create(
        staff_id="2026-00002",
        full_name="John Smith",
        designation="Photojournalist",
    )

    att_repo = AttendanceRepository(temp_db)
    session_id = att_repo.create_session(
        staff_id=staff_id,
        category="Duty",
        status="OPEN",
    )
    assert session_id > 0

    session = att_repo.get_by_id(session_id)
    assert session is not None
    assert session["status"] == "OPEN"

    # Close session
    closed = att_repo.close_session(session_id)
    assert closed is True

    updated_session = att_repo.get_by_id(session_id)
    assert updated_session["status"] == "COMPLETED"
    assert updated_session["time_out"] is not None


def test_auth_service_password_only(temp_db):
    auth_service = AuthService(temp_db)
    # Ensures default admin exists and checks TGPQR_2026
    admin = auth_service.authenticate("TGPQR_2026")
    assert admin is not None
    assert admin["username"] == "admin"

    # Wrong password raises AuthenticationError
    from src.core.exceptions import AuthenticationError
    with pytest.raises(AuthenticationError):
        auth_service.authenticate("WrongPassword")
