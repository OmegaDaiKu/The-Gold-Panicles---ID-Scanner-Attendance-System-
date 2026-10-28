""""Repository for attendance session CRUD, metrics, and overdue detection."""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from src.utils.time_utils import PHT_TIMEZONE

logger = logging.getLogger(__name__)


class AttendanceRepository:
    def __init__(self, db_connection):
        self.conn = db_connection

    def _get_connection(self) -> sqlite3.Connection:
        if hasattr(self.conn, 'get_connection'):
            return self.conn.get_connection()
        if hasattr(self.conn, 'conn'):
            return self.conn.conn
        return self.conn

    @contextmanager
    def _db_scope(self):
        if hasattr(self.conn, "transaction"):
            with self.conn.transaction() as conn:
                yield conn
        else:
            conn = self._get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _resolve_staff_join(self, cursor) -> Tuple[bool, str, str, str]:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff'")
        has_staff = cursor.fetchone() is not None
        if not has_staff:
            return False, "", "", ""

        cursor.execute("PRAGMA table_info(staff)")
        cols = [row[1] for row in cursor.fetchall()]
        name_col = "full_name" if "full_name" in cols else "name"
        desig_col = "designation" if "designation" in cols else "primary_designation"
        sid_col = "student_id_no" if "student_id_no" in cols else ("staff_id" if "staff_id" in cols else "id")
        return True, sid_col, name_col, desig_col

    def get_dashboard_metrics(self) -> Dict[str, int]:
        with self._db_scope() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(DISTINCT staff_id) FROM attendance_sessions WHERE status = 'OPEN'"
            )
            staff_in_office = cursor.fetchone()[0] or 0

            cursor.execute(
                "SELECT COUNT(*) FROM visitor_visits WHERE status = 'OPEN'"
            )
            active_visitors = cursor.fetchone()[0] or 0

            cursor.execute(
                "SELECT COUNT(*) FROM attendance_sessions WHERE status = 'OVERDUE'"
            )
            overdue_sessions = cursor.fetchone()[0] or 0

            query_total_entries = """
                SELECT 
                    (SELECT COUNT(*) FROM attendance_sessions
                     WHERE date(time_in, '+8 hours') = date('now', '+8 hours')) +
                    (SELECT COUNT(*) FROM visitor_visits
                     WHERE date(time_in, '+8 hours') = date('now', '+8 hours'))
                AS total_entries_today
            """
            cursor.execute(query_total_entries)
            total_entries_today = cursor.fetchone()[0] or 0

            return {
                "staff_in_office": staff_in_office,
                "active_visitors": active_visitors,
                "overdue_sessions": overdue_sessions,
                "total_entries_today": total_entries_today,
            }

    def create_session(
        self,
        staff_id: int,
        category,
        time_in: Optional[str] = None,
        status: str = "OPEN",
        **kwargs,
    ) -> int:
        cat_str = category.value if hasattr(category, 'value') else str(category)

        if time_in is None:
            time_in = datetime.now(timezone.utc).isoformat()

        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(attendance_sessions)")
            col_info = {row[1]: (row[2] or "TEXT").upper() for row in cursor.fetchall()}

            if col_info.get("time_in") in ("INTEGER", "INT"):
                try:
                    dt = datetime.fromisoformat(str(time_in).replace("Z", "+00:00"))
                    time_in = int(dt.timestamp())
                except (ValueError, AttributeError):
                    pass

            columns = ["staff_id", "time_in", "status"]
            values = [staff_id, time_in, status]

            if "category" in col_info:
                columns.append("category")
                values.append(cat_str)

            if "created_at" in col_info:
                now_val = datetime.now(timezone.utc).isoformat()
                if col_info["created_at"] in ("INTEGER", "INT"):
                    now_val = int(datetime.now(timezone.utc).timestamp())
                columns.append("created_at")
                values.append(now_val)

            cols_sql = ", ".join(columns)
            placeholders = ", ".join(["?"] * len(values))
            query = f"INSERT INTO attendance_sessions ({cols_sql}) VALUES ({placeholders})"

            cursor.execute(query, values)
            return cursor.lastrowid

    def get_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attendance_sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

    def close_session(self, session_id: int, time_out: Optional[str] = None) -> bool:
        """Closes an OPEN or OVERDUE attendance session as COMPLETED.

        FIXED THIS SESSION: previously this UPDATE had no status guard at all
        (`WHERE id = ?` only), meaning it would silently overwrite a session
        that was already COMPLETED or RESOLVED -- clobbering its time_out and
        status with no concurrency protection and no audit trail, unlike
        OverdueService.resolve_staff_session()/resolve_visitor_visit(), which
        both correctly guard on status with a rowcount check. Now guarded the
        same way: only rows still in OPEN or OVERDUE are affected, and the
        caller (AttendanceService.confirm_staff_time_out) is expected to act
        on the returned bool rather than assume success.
        """
        if time_out is None:
            time_out = datetime.now(timezone.utc).isoformat()

        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(attendance_sessions)")
            col_info = {row[1]: (row[2] or "TEXT").upper() for row in cursor.fetchall()}

            if col_info.get("time_out") in ("INTEGER", "INT"):
                try:
                    dt = datetime.fromisoformat(str(time_out).replace("Z", "+00:00"))
                    time_out = int(dt.timestamp())
                except (ValueError, AttributeError):
                    pass

            if "updated_at" in col_info:
                now_val = datetime.now(timezone.utc).isoformat()
                if col_info.get("updated_at") in ("INTEGER", "INT"):
                    now_val = int(datetime.now(timezone.utc).timestamp())
                cursor.execute(
                    "UPDATE attendance_sessions SET time_out = ?, status = 'COMPLETED', updated_at = ? "
                    "WHERE id = ? AND status IN ('OPEN', 'OVERDUE')",
                    (time_out, now_val, session_id),
                )
            else:
                cursor.execute(
                    "UPDATE attendance_sessions SET time_out = ?, status = 'COMPLETED' "
                    "WHERE id = ? AND status IN ('OPEN', 'OVERDUE')",
                    (time_out, session_id),
                )
            return cursor.rowcount > 0

    def get_recent_sessions(self, limit: Optional[int] = 50) -> List[Dict[str, Any]]:
        with self._db_scope() as conn:
            cursor = conn.cursor()

            has_staff, sid_col, name_col, desig_col = self._resolve_staff_join(cursor)

            if has_staff:
                query = f"""
                    SELECT 
                        a.*, 
                        s.{sid_col} AS student_id_no,
                        s.{name_col} AS full_name,
                        s.{desig_col} AS designation
                    FROM attendance_sessions a
                    LEFT JOIN staff s ON a.staff_id = s.id OR a.staff_id = s.{sid_col}
                    ORDER BY a.time_in DESC
                """
            else:
                query = "SELECT *, staff_id AS student_id_no, 'Staff' AS full_name, 'Staffer' AS designation FROM attendance_sessions ORDER BY time_in DESC"

            params: tuple = ()
            if limit is not None:
                query += " LIMIT ?"
                params = (limit,)

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_session(self, session_id: int, **kwargs) -> bool:
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(attendance_sessions)")
            col_info = {row[1]: (row[2] or "TEXT").upper() for row in cursor.fetchall()}
            col_names = set(col_info.keys())
            fields = []
            values = []
            for col in ["category", "status", "time_out", "resolution_notes"]:
                if col in col_names and col in kwargs:
                    value = kwargs[col]
                    if value is not None and col == "time_out" and col_info.get("time_out") in ("INTEGER", "INT"):
                        try:
                            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                            value = int(dt.timestamp())
                        except (ValueError, AttributeError):
                            pass
                    fields.append(f"{col} = ?")
                    values.append(value)

            if not fields:
                return False

            if "updated_at" in col_names:
                now_val = datetime.now(timezone.utc).isoformat()
                if col_info.get("updated_at") in ("INTEGER", "INT"):
                    now_val = int(datetime.now(timezone.utc).timestamp())
                fields.append("updated_at = ?")
                values.append(now_val)

            values.append(session_id)
            cursor.execute(f"UPDATE attendance_sessions SET {', '.join(fields)} WHERE id = ?", values)
            return cursor.rowcount > 0

    def delete_session(self, session_id: int) -> bool:
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance_sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

    def flag_overdue_sessions(self, cutoff_hours: int = 12) -> int:
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(attendance_sessions)")
            col_info = {row[1]: (row[2] or "TEXT").upper() for row in cursor.fetchall()}

            cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)

            now_pht = datetime.now(PHT_TIMEZONE)
            midnight_pht = now_pht.replace(hour=0, minute=0, second=0, microsecond=0)
            midnight_utc_dt = midnight_pht.astimezone(timezone.utc)

            if col_info.get("time_in") in ("INTEGER", "INT"):
                cutoff_value = int(cutoff_dt.timestamp())
                midnight_value = int(midnight_utc_dt.timestamp())
            else:
                cutoff_value = cutoff_dt.isoformat()
                midnight_value = midnight_utc_dt.isoformat()

            cursor.execute(
                """
                UPDATE attendance_sessions
                SET status = 'OVERDUE'
                WHERE status = 'OPEN' AND (time_in <= ? OR time_in < ?)
                """,
                (cutoff_value, midnight_value),
            )
            return cursor.rowcount

    def auto_resolve_stale_overdue_sessions(self, grace_hours: int = 72) -> List[Dict[str, Any]]:
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(attendance_sessions)")
            col_info = {row[1]: (row[2] or "TEXT").upper() for row in cursor.fetchall()}
            col_names = set(col_info.keys())
            is_integer_time = col_info.get("time_in") in ("INTEGER", "INT")
            has_resolution_notes_col = "resolution_notes" in col_names

            select_cols = ["id", "time_in", "time_out"]
            if has_resolution_notes_col:
                select_cols.append("resolution_notes")

            cursor.execute(
                f"SELECT {', '.join(select_cols)} FROM attendance_sessions WHERE status = 'OVERDUE'"
            )
            candidates = cursor.fetchall()

            note = (
                f"Auto-resolved by system — unresolved after {grace_hours} hours "
                f"past time-in. Administrator review recommended."
            )

            now_utc = datetime.now(timezone.utc)
            resolved_records: List[Dict[str, Any]] = []

            for row in candidates:
                session_id = row[0]
                time_in_raw = row[1]
                old_time_out = row[2]
                old_resolution_notes = row[3] if has_resolution_notes_col else None

                try:
                    if is_integer_time:
                        time_in_dt = datetime.fromtimestamp(int(time_in_raw), tz=timezone.utc)
                    else:
                        time_in_dt = datetime.fromisoformat(str(time_in_raw).replace("Z", "+00:00"))
                        if time_in_dt.tzinfo is None:
                            time_in_dt = time_in_dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError, OSError, OverflowError):
                    logger.warning(
                        "auto_resolve_stale_overdue_sessions: could not parse "
                        "time_in '%s' for session id=%s -- skipping.",
                        time_in_raw, session_id,
                    )
                    continue

                grace_cutoff_dt = time_in_dt + timedelta(hours=grace_hours)
                if now_utc < grace_cutoff_dt:
                    continue

                if is_integer_time:
                    time_out_value = int(grace_cutoff_dt.timestamp())
                else:
                    time_out_value = grace_cutoff_dt.isoformat()

                fields = ["status = 'COMPLETED'", "time_out = ?"]
                values: list = [time_out_value]

                if has_resolution_notes_col:
                    fields.append("resolution_notes = ?")
                    values.append(note)

                if "updated_at" in col_names:
                    now_val = now_utc.isoformat()
                    if col_info.get("updated_at") in ("INTEGER", "INT"):
                        now_val = int(now_utc.timestamp())
                    fields.append("updated_at = ?")
                    values.append(now_val)

                values.append(session_id)

                cursor.execute(
                    f"UPDATE attendance_sessions SET {', '.join(fields)} "
                    f"WHERE id = ? AND status = 'OVERDUE'",
                    values,
                )

                if cursor.rowcount > 0:
                    old_values: Dict[str, Any] = {"status": "OVERDUE", "time_out": old_time_out}
                    new_values: Dict[str, Any] = {"status": "COMPLETED", "time_out": time_out_value}
                    if has_resolution_notes_col:
                        old_values["resolution_notes"] = old_resolution_notes
                        new_values["resolution_notes"] = note

                    resolved_records.append({
                        "id": session_id,
                        "old_values": old_values,
                        "new_values": new_values,
                    })

            return resolved_records

    def query_sessions(
        self,
        staff_id: Optional[int] = None,
        status: Optional[str] = None,
        date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        with self._db_scope() as conn:
            cursor = conn.cursor()

            has_staff, sid_col, name_col, desig_col = self._resolve_staff_join(cursor)

            if has_staff:
                query = f"""
                    SELECT
                        a.*,
                        s.{sid_col} AS student_id_no,
                        s.{name_col} AS full_name,
                        s.{desig_col} AS designation
                    FROM attendance_sessions a
                    LEFT JOIN staff s ON a.staff_id = s.id OR a.staff_id = s.{sid_col}
                """
            else:
                query = (
                    "SELECT a.*, a.staff_id AS student_id_no, 'Staff' AS full_name, "
                    "'Staffer' AS designation FROM attendance_sessions a"
                )

            params: list = []
            conditions: list = []

            if staff_id is not None:
                conditions.append("a.staff_id = ?")
                params.append(staff_id)
            if status is not None:
                conditions.append("a.status = ?")
                params.append(status)
            if date is not None:
                conditions.append("date(a.time_in, '+8 hours') = ?")
                params.append(date)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY a.time_in DESC"

            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_distinct_session_dates(self) -> List[str]:
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT date(time_in, '+8 hours') AS d "
                "FROM attendance_sessions WHERE time_in IS NOT NULL"
            )
            return [row[0] for row in cursor.fetchall() if row[0] is not None]