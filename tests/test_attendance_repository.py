from src.database.repositories.attendance_repo import AttendanceRepository


def test_staff_session_can_be_created_and_retrieved(db_manager, sample_staff):
    repo = AttendanceRepository(db_manager)
    session_id = repo.create_session(
        staff_id=sample_staff,
        category="Duty",
        time_in="2026-01-15T01:00:00+00:00",
    )

    record = repo.get_by_id(session_id)
    assert record is not None
    assert record["staff_id"] == sample_staff
    assert record["category"] == "Duty"
    assert record["status"] == "OPEN"
    assert record["time_out"] is None


def test_open_session_can_be_closed(db_manager, sample_staff):
    repo = AttendanceRepository(db_manager)
    session_id = repo.create_session(
        staff_id=sample_staff,
        category="Visit",
        time_in="2026-01-15T01:00:00+00:00",
    )

    closed = repo.close_session(
        session_id,
        time_out="2026-01-15T03:00:00+00:00",
    )

    record = repo.get_by_id(session_id)
    assert closed is True
    assert record["status"] == "COMPLETED"
    assert record["time_out"] == "2026-01-15T03:00:00+00:00"


def test_completed_session_cannot_be_closed_or_overwritten_again(db_manager, sample_staff):
    repo = AttendanceRepository(db_manager)
    session_id = repo.create_session(sample_staff, "Duty")
    assert repo.close_session(session_id, "2026-01-15T03:00:00+00:00") is True

    assert repo.close_session(session_id, "2026-01-15T04:00:00+00:00") is False
    record = repo.get_by_id(session_id)
    assert record["time_out"] == "2026-01-15T03:00:00+00:00"
    assert record["status"] == "COMPLETED"


def test_closing_unknown_session_returns_false(db_manager):
    repo = AttendanceRepository(db_manager)
    assert repo.close_session(999999, "2026-01-15T03:00:00+00:00") is False
