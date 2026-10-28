"""Unit tests verifying business logic services, validation, state transitions, and Argon2id authentication."""

import pytest
from src.core.constants import OFFICIAL_DESIGNATIONS
from src.core.exceptions import AuthenticationError, DuplicateRecordError, InvalidStateError, ValidationError
from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer
from src.services.directory_service import DirectoryService
from src.services.attendance_service import AttendanceService
from src.services.auth_service import AuthService
from src.services.overdue_service import OverdueService


@pytest.fixture
def temp_db(tmp_path):
    """Provides a clean temporary database instance."""
    db_file = tmp_path / "test_services.db"
    db_manager = DatabaseConnectionManager(str(db_file))
    schema = SchemaInitializer(db_manager)
    schema.ensure_schema_exists()
    yield db_manager
    db_manager.close()


def test_directory_service_crud_and_designations(temp_db):
    """Verifies directory registration and validation against official 22 designations."""
    dir_service = DirectoryService(temp_db)

    # Valid Registration
    staff = dir_service.register_staff("261-00105", "Jules Leo Reserva", "Editor-in-Chief")
    assert staff["student_id_no"] == "261-00105"
    assert staff["designation"] == "Editor-in-Chief"

    # Duplicate Registration -> Must fail
    with pytest.raises(DuplicateRecordError):
        dir_service.register_staff("261-00105", "Duplicate Person", "News Writer")

    # Invalid Designation -> Must fail
    with pytest.raises(ValidationError):
        dir_service.register_staff("261-00999", "Fake Staff", "Invalid Designation Role")


def test_attendance_service_evaluation_and_explicit_confirmations(temp_db):
    """Verifies scanning evaluation workflow and explicit confirmation state transitions."""
    dir_service = DirectoryService(temp_db)
    att_service = AttendanceService(temp_db)

    staff = dir_service.register_staff("261-00105", "Jules Leo Reserva", "Editor-in-Chief")

    # 1. Scan active staff with no open session
    eval1 = att_service.evaluate_scanned_id("261-00105")
    assert eval1["type"] == "STAFF_TIME_IN_SELECT_CATEGORY"

    # 2. Confirm Time-In
    session = att_service.confirm_staff_time_in(staff["id"], category="Duty")
    assert session["status"] == "OPEN"
    assert session["time_out"] is None

    # 3. Scan active staff WITH open session -> Must request Time-Out
    eval2 = att_service.evaluate_scanned_id("261-00105")
    assert eval2["type"] == "STAFF_TIME_OUT_REQUIRED"

    # 4. Confirm Time-Out
    completed = att_service.confirm_staff_time_out(session["id"])
    assert completed["status"] == "COMPLETED"
    assert completed["time_out"] is not None


def test_auth_service_argon2id(temp_db):
    """Verifies Argon2id password hashing and default admin seeding."""
    auth_service = AuthService(temp_db)

    # Ensure default admin exists
    admin = auth_service.ensure_default_admin_exists()
    assert admin["username"] == "admin"

    # Authenticate with correct password
    authed = auth_service.authenticate("admin", "AdminPassword123!")
    assert authed["username"] == "admin"

    # Authenticate with invalid password -> Must raise AuthenticationError
    with pytest.raises(AuthenticationError):
        auth_service.authenticate("admin", "WrongPassword")