"""Repository DAO for Guest Visitor visits database operations."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from src.database.connection import DatabaseConnectionManager
from src.utils.time_utils import get_utc_now_iso, PHT_TIMEZONE

logger = logging.getLogger(__name__)


class VisitorRepository:
    """Data access object for guest visitor records."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager

    def create_visit(self, student_id_no: str, visitor_name: str, time_in: str, category: str = "Visit") -> int:
        sql = """
            INSERT INTO visitor_visits (student_id_no, visitor_name, category, time_in, status, created_at)
            VALUES (?, ?, ?, ?, 'OPEN', ?);
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (student_id_no, visitor_name, category, time_in, time_in))
            return cursor.lastrowid

    def get_open_visit_by_student_id(self, student_id_no: str) -> Optional[Dict]:
        sql = "SELECT id, student_id_no, visitor_name, category, time_in, time_out, status FROM visitor_visits WHERE student_id_no = ? AND status = 'OPEN';"
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (student_id_no,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_by_id(self, visit_id: int) -> Optional[Dict]:
        sql = "SELECT id, student_id_no, visitor_name, category, time_in, time_out, status, resolution_notes FROM visitor_visits WHERE id = ?;"
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (visit_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def close_visit(self, visit_id: int, time_out: str) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("PRAGMA table_info(visitor_visits)")
            col_info = {str(row[1]): (row[2] or "TEXT").upper() for row in cursor.fetchall()}

            time_out_value = time_out
            if col_info.get("time_out") in ("INTEGER", "INT"):
                try:
                    dt = datetime.fromisoformat(str(time_out).replace("Z", "+00:00"))
                    time_out_value = int(dt.timestamp())
                except (ValueError, AttributeError):
                    pass

            updated_at_value = get_utc_now_iso()
            if col_info.get("updated_at") in ("INTEGER", "INT"):
                try:
                    updated_at_value = int(datetime.now(timezone.utc).timestamp())
                except (ValueError, AttributeError):
                    pass

            cursor = conn.execute(
                """
                UPDATE visitor_visits
                SET time_out = ?, status = 'COMPLETED', updated_at = ?
                WHERE id = ? AND status IN ('OPEN', 'OVERDUE');
                """,
                (time_out_value, updated_at_value, visit_id),
            )
            return cursor.rowcount > 0

    def update_visit(self, visit_id: int, **kwargs) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("PRAGMA table_info(visitor_visits)")
            col_info = {str(row[1]): (row[2] or "TEXT").upper() for row in cursor.fetchall()}
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
                now_val = get_utc_now_iso()
                if col_info.get("updated_at") in ("INTEGER", "INT"):
                    try:
                        now_val = int(datetime.now(timezone.utc).timestamp())
                    except (ValueError, AttributeError):
                        pass
                fields.append("updated_at = ?")
                values.append(now_val)

            values.append(visit_id)
            cursor = conn.execute(
                f"UPDATE visitor_visits SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            return cursor.rowcount > 0

    def delete_visit(self, visit_id: int) -> bool:
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM visitor_visits WHERE id = ?", (visit_id,))
            return cursor.rowcount > 0

    def query_visits(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        status: Optional[str] = None,
        date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        conditions = []
        params = []

        if start_time:
            conditions.append("time_in >= ?")
            params.append(start_time)
        if end_time:
            conditions.append("time_in <= ?")
            params.append(end_time)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if date:
            conditions.append("date(time_in, '+8 hours') = ?")
            params.append(date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT id, student_id_no, visitor_name, category, time_in, time_out, status, resolution_notes FROM visitor_visits {where_clause} ORDER BY time_in DESC"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        sql += ";"

        with self.db.transaction() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def flag_overdue_visits(self, cutoff_hours: int = 12) -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute("PRAGMA table_info(visitor_visits)")
            col_info = {str(row[1]): (row[2] or "TEXT").upper() for row in cursor.fetchall()}

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

            cursor = conn.execute(
                """
                UPDATE visitor_visits
                SET status = 'OVERDUE'
                WHERE status = 'OPEN' AND (time_in <= ? OR time_in < ?)
                """,
                (cutoff_value, midnight_value),
            )
            return cursor.rowcount

    def auto_resolve_stale_overdue_visits(self, grace_hours: int = 72) -> List[Dict[str, Any]]:
        resolution_marker = (
            f"Auto-resolved by system — unresolved after {grace_hours} hours "
            "past time-in. Administrator review recommended."
        )

        with self.db.transaction() as conn:
            cursor = conn.execute("PRAGMA table_info(visitor_visits)")
            col_info = {str(row[1]): (row[2] or "TEXT").upper() for row in cursor.fetchall()}
            col_names = set(col_info.keys())

            time_in_is_epoch = col_info.get("time_in") in ("INTEGER", "INT")
            time_out_is_epoch = col_info.get("time_out") in ("INTEGER", "INT")
            updated_at_is_epoch = col_info.get("updated_at") in ("INTEGER", "INT")
            has_resolution_notes = "resolution_notes" in col_names
            has_updated_at = "updated_at" in col_names

            select_cols = ["id", "time_in", "time_out"]
            if has_resolution_notes:
                select_cols.append("resolution_notes")

            cursor = conn.execute(
                f"SELECT {', '.join(select_cols)} FROM visitor_visits WHERE status = 'OVERDUE';"
            )
            rows = cursor.fetchall()

            now_utc = datetime.now(timezone.utc)
            resolved_records: List[Dict[str, Any]] = []

            for row in rows:
                visit_id = row[0]
                raw_time_in = row[1]
                old_time_out = row[2]
                old_resolution_notes = row[3] if has_resolution_notes else None

                try:
                    if time_in_is_epoch:
                        time_in_dt = datetime.fromtimestamp(int(raw_time_in), tz=timezone.utc)
                    else:
                        time_in_dt = datetime.fromisoformat(str(raw_time_in).replace("Z", "+00:00"))
                        if time_in_dt.tzinfo is None:
                            time_in_dt = time_in_dt.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError, OSError):
                    logger.warning(
                        "auto_resolve_stale_overdue_visits: could not parse time_in "
                        "(%r) for visitor_visits.id=%s -- skipping.",
                        raw_time_in, visit_id,
                    )
                    continue

                grace_cutoff_dt = time_in_dt + timedelta(hours=grace_hours)
                if now_utc < grace_cutoff_dt:
                    continue

                time_out_value = (
                    int(grace_cutoff_dt.timestamp()) if time_out_is_epoch
                    else grace_cutoff_dt.isoformat()
                )

                set_clauses = ["status = 'COMPLETED'", "time_out = ?"]
                params = [time_out_value]

                if has_resolution_notes:
                    set_clauses.append("resolution_notes = ?")
                    params.append(resolution_marker)

                if has_updated_at:
                    updated_at_value = (
                        int(now_utc.timestamp()) if updated_at_is_epoch
                        else now_utc.isoformat()
                    )
                    set_clauses.append("updated_at = ?")
                    params.append(updated_at_value)

                params.append(visit_id)

                update_cursor = conn.execute(
                    f"UPDATE visitor_visits SET {', '.join(set_clauses)} "
                    "WHERE id = ? AND status = 'OVERDUE';",
                    params,
                )
                if update_cursor.rowcount > 0:
                    old_values: Dict[str, Any] = {"status": "OVERDUE", "time_out": old_time_out}
                    new_values: Dict[str, Any] = {"status": "COMPLETED", "time_out": time_out_value}
                    if has_resolution_notes:
                        old_values["resolution_notes"] = old_resolution_notes
                        new_values["resolution_notes"] = resolution_marker

                    resolved_records.append({
                        "id": visit_id,
                        "old_values": old_values,
                        "new_values": new_values,
                    })

            return resolved_records

    def get_distinct_visit_dates(self) -> List[str]:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT date(time_in, '+8 hours') AS d "
                "FROM visitor_visits WHERE time_in IS NOT NULL;"
            )
            return [row[0] for row in cursor.fetchall() if row[0] is not None]