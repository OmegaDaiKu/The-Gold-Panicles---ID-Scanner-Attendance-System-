import sqlite3

import pytest

from src.database.repositories.attendance_repo import AttendanceRepository


def test_schema_initializer_creates_expected_tables(db_manager):
    with db_manager.transaction() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    table_names = {row["name"] for row in rows}

    assert {
        "staff",
        "attendance_sessions",
        "visitor_visits",
        "admin_users",
        "audit_logs",
    }.issubset(table_names)


def test_database_enforces_foreign_keys(db_manager):
    with pytest.raises(sqlite3.IntegrityError):
        with db_manager.transaction() as conn:
            conn.execute(
                """
                INSERT INTO attendance_sessions
                    (staff_id, category, time_in, status, created_at)
                VALUES (?, 'Duty', ?, 'OPEN', ?)
                """,
                (999999, "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
            )


def test_transaction_commits_successful_changes(db_manager):
    with db_manager.transaction() as conn:
        conn.execute(
            """
            INSERT INTO staff
                (student_id_no, full_name, designation, is_active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            ("261-00001", "Committed User", "News Writer", "2026-01-01T00:00:00+00:00"),
        )

    with db_manager.transaction() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM staff WHERE student_id_no = ?",
            ("261-00001",),
        ).fetchone()[0]

    assert count == 1


def test_transaction_rolls_back_when_exception_occurs(db_manager):
    with pytest.raises(RuntimeError):
        with db_manager.transaction() as conn:
            conn.execute(
                """
                INSERT INTO staff
                    (student_id_no, full_name, designation, is_active, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                ("261-00002", "Rolled Back User", "News Writer", "2026-01-01T00:00:00+00:00"),
            )
            raise RuntimeError("Force rollback")

    with db_manager.transaction() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM staff WHERE student_id_no = ?",
            ("261-00002",),
        ).fetchone()[0]

    assert count == 0


def test_only_one_open_staff_session_is_allowed(db_manager, sample_staff):
    repo = AttendanceRepository(db_manager)
    first_id = repo.create_session(sample_staff, "Duty")

    assert first_id > 0
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_session(sample_staff, "Visit")
