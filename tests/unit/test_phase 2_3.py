"""Unit tests for Phase 2 & 3 redesign (Designation support & Live Board Feed)."""

import pytest

from src.core.constants import AttendanceCategory
from src.services.attendance_service import AttendanceService
from src.services.directory_service import DirectoryService


def test_directory_service_designation(temp_db):
    """Verifies registration and info update with publication designation."""
    dir_service = DirectoryService(temp_db)

    staff = dir_service.register_staff("261-00105", "John Brian Escol", designation="Editor-in-Chief")
    assert staff["designation"] == "Editor-in-Chief"

    updated = dir_service.update_staff_info(staff["id"], "John Brian Escol", designation="Managing Editor")
    assert updated["designation"] == "Managing Editor"


def test_live_attendance_feed_and_stats(temp_db):
    """Verifies live board feed generation and primary ID stripping."""
    dir_service = DirectoryService(temp_db)
    att_service = AttendanceService(temp_db)

    staff = dir_service.register_staff("261-00105", "John Brian Escol", designation="Editor-in-Chief")
    att_service.confirm_staff_time_in(staff["id"], AttendanceCategory.DUTY)

    att_service.confirm_visitor_time_in("261-99999", "Guest Visitor")

    feed = att_service.get_live_attendance_feed()
    assert len(feed) == 2
    
    # Primary DB 'id' must NOT be exposed in live feed dict
    assert "id" not in feed[0]
    assert feed[0]["designation"] in ["Editor-in-Chief", "Guest Visitor"]

    stats = att_service.get_quick_stats()
    assert stats["active_duty_staff"] == 1
    assert stats["active_visitors"] == 1