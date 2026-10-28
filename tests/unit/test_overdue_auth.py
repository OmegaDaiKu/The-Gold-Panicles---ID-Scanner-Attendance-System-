"""Unit tests verifying Argon2id authentication and overdue cutoff processing."""

import pytest

from src.core.constants import AttendanceCategory, SessionStatus
from src.core.exceptions import AuthenticationError
from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.staff_repo import StaffRepository
from src.services.auth_service import AuthService
from src.services.overdue_service import OverdueService


def test_auth_service_argon2_hashing(temp_db):
    """Verifies Argon2id user account creation and password authentication."""
    auth_service = AuthService(temp_db)

    assert auth_service.is_setup_required() is True

    # Create Master Admin
    admin = auth_service.create_admin(
        creator_admin_id=None,
        username="admin",
        plain_password="SecurePassword123!",
    )
    assert admin["username"] == "admin"
    assert auth_service.is_setup_required() is False

    # Authenticate valid credentials
    logged_in = auth_service.authenticate("admin", "SecurePassword123!")
    assert logged_in["id"] == admin["id"]

    # Reject invalid password
    with pytest.raises(AuthenticationError):
        auth_service.authenticate("admin", "WrongPassword")


def test_overdue_detection_and_resolution(temp_db):
    """Verifies midnight cutoff flagging and administrative session resolution."""
    auth_service = AuthService(temp_db)
    staff_repo = StaffRepository(temp_db)
    att_repo = AttendanceRepository(temp_db)
    overdue_service = OverdueService(temp_db)

    # 1. Create an admin user first so admin_id satisfies foreign key constraint in audit_logs
    admin = auth_service.create_admin(
        creator_admin_id=None,
        username="admin_resolver",
        plain_password="SecurePassword123!",
    )
    admin_id = admin["id"]

    # 2. Register staff member
    staff_id = staff_repo.create("261-00105", "John Brian Escol", "2026-10-15T08:00:00Z")
    
    # 3. Create an old session started yesterday (2026-10-15T08:00:00Z)
    old_session_id = att_repo.create_session(staff_id, AttendanceCategory.DUTY, "2026-10-15T08:00:00Z")

    # 4. Run overdue detector
    summary = overdue_service.check_and_flag_overdue_records()
    assert summary["flagged_staff_sessions"] == 1

    # 5. Verify status transitioned to OVERDUE
    session = att_repo.get_by_id(old_session_id)
    assert session["status"] == SessionStatus.OVERDUE.value

    # 6. Admin resolves session with verified time-out
    resolved = overdue_service.resolve_staff_session(
        admin_id=admin_id,
        session_id=old_session_id,
        verified_time_out="2026-10-15T17:00:00Z",
        reason="Verified departure via office logs.",
    )
    assert resolved["status"] == SessionStatus.RESOLVED.value
    assert resolved["time_out"] == "2026-10-15T17:00:00Z"