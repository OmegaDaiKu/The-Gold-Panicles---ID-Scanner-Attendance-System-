"""Service for identifying and processing overdue attendance sessions."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.core.constants import SessionStatus
from src.core.exceptions import InvalidStateError, RecordNotFoundError
from src.database.connection import DatabaseConnectionManager
from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.visitor_repo import VisitorRepository
from src.services.audit_service import AuditService
from src.utils.time_utils import get_utc_now_iso, format_iso_to_pht


def _format_overdue_duration(time_in_iso: Optional[str]) -> str:
    """Formats elapsed time since `time_in_iso` as a human-readable 'overdue' duration string."""
    if not time_in_iso:
        return "Overdue"
    try:
        normalized = time_in_iso.replace("Z", "+00:00")
        start = datetime.fromisoformat(normalized)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta_seconds = max(0, int((now - start).total_seconds()))
        total_minutes = delta_seconds // 60
        days, remainder = divmod(total_minutes, 1440)
        hours, minutes = divmod(remainder, 60)

        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts) + " overdue"
    except (ValueError, TypeError):
        return "Overdue"


class OverdueService:
    """Handles automatic detection, flagging, and administrative resolution of overdue sessions."""

    RESOLVABLE_STATUSES = {SessionStatus.OPEN.value, SessionStatus.OVERDUE.value, "OPEN", "OVERDUE"}

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager
        self.att_repo = AttendanceRepository(db_manager)
        self.attendance_repo = self.att_repo
        self.vis_repo = VisitorRepository(db_manager)
        self.visitor_repo = self.vis_repo
        self.audit_service = AuditService(db_manager)

    def check_and_flag_overdue_records(self, cutoff_hours: int = 12) -> Dict[str, int]:
        """Scans active open sessions exceeding duration thresholds and flags them as OVERDUE."""
        flagged_staff = self.att_repo.flag_overdue_sessions(cutoff_hours=cutoff_hours)
        flagged_vis = self.vis_repo.flag_overdue_visits(cutoff_hours=cutoff_hours)
        total_flagged = flagged_staff + flagged_vis

        return {
            "flagged_count": total_flagged,
            "flagged_staff_sessions": flagged_staff,
            "flagged_visitor_visits": flagged_vis,
        }

    def scan_and_flag_overdue_records(self) -> Dict[str, int]:
        """Alias for check_and_flag_overdue_records."""
        return self.check_and_flag_overdue_records()

    def resolve_staff_session(
        self,
        admin_id: int,
        session_id: int,
        verified_time_out: Optional[str] = None,
        reason: str = "",
    ) -> Dict:
        """Resolves an overdue or open staff attendance session with an administrator reason."""
        session = self.att_repo.get_by_id(session_id)
        if not session:
            raise RecordNotFoundError(f"Attendance session {session_id} not found.")

        current_status = session.get("status")
        if current_status not in self.RESOLVABLE_STATUSES:
            raise InvalidStateError(
                f"Attendance session {session_id} is already '{current_status}' and cannot be resolved again."
            )

        time_out_val = verified_time_out if verified_time_out else get_utc_now_iso()
        now_iso = get_utc_now_iso()

        status_list = list(self.RESOLVABLE_STATUSES)
        placeholders = ", ".join(["?"] * len(status_list))
        sql = f"""
            UPDATE attendance_sessions
            SET status = 'RESOLVED', time_out = ?, resolution_notes = ?, updated_at = ?
            WHERE id = ? AND status IN ({placeholders});
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (time_out_val, reason, now_iso, session_id, *status_list))

            if cursor.rowcount == 0:
                raise InvalidStateError(
                    f"Attendance session {session_id} could not be resolved — its status "
                    f"changed concurrently before this action completed. Please refresh "
                    f"the list and try again."
                )

            self.audit_service.log_action(
                admin_id=admin_id,
                action_type="RESOLVE_OVERDUE",
                entity_type="attendance_sessions",
                entity_id=session_id,
                reason=reason if reason else "Admin resolved overdue session",
                old_values={"status": session.get("status"), "time_out": session.get("time_out")},
                new_values={"status": "RESOLVED", "time_out": time_out_val, "resolution_notes": reason},
            )

        return self.att_repo.get_by_id(session_id)

    def resolve_overdue_staff_session(
        self,
        admin_id: int,
        session_id: int,
        manual_time_out_iso: Optional[str] = None,
        reason: str = "",
    ) -> Dict:
        """Alias for resolve_staff_session."""
        return self.resolve_staff_session(
            admin_id=admin_id,
            session_id=session_id,
            verified_time_out=manual_time_out_iso,
            reason=reason,
        )

    def resolve_visitor_visit(
        self,
        admin_id: int,
        visit_id: int,
        verified_time_out: Optional[str] = None,
        reason: str = "",
    ) -> Dict:
        """Resolves an overdue or open visitor visit with an administrator reason."""
        visit = self.vis_repo.get_by_id(visit_id)
        if not visit:
            raise RecordNotFoundError(f"Visitor visit {visit_id} not found.")

        current_status = visit.get("status")
        if current_status not in self.RESOLVABLE_STATUSES:
            raise InvalidStateError(
                f"Visitor visit {visit_id} is already '{current_status}' and cannot be resolved again."
            )

        time_out_val = verified_time_out if verified_time_out else get_utc_now_iso()
        now_iso = get_utc_now_iso()

        status_list = list(self.RESOLVABLE_STATUSES)
        placeholders = ", ".join(["?"] * len(status_list))
        sql = f"""
            UPDATE visitor_visits
            SET status = 'RESOLVED', time_out = ?, resolution_notes = ?, updated_at = ?
            WHERE id = ? AND status IN ({placeholders});
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (time_out_val, reason, now_iso, visit_id, *status_list))

            if cursor.rowcount == 0:
                raise InvalidStateError(
                    f"Visitor visit {visit_id} could not be resolved — its status "
                    f"changed concurrently before this action completed. Please refresh "
                    f"the list and try again."
                )

            self.audit_service.log_action(
                admin_id=admin_id,
                action_type="RESOLVE_OVERDUE",
                entity_type="visitor_visits",
                entity_id=visit_id,
                reason=reason if reason else "Admin resolved overdue visitor visit",
                old_values={"status": visit.get("status"), "time_out": visit.get("time_out")},
                new_values={"status": "RESOLVED", "time_out": time_out_val, "resolution_notes": reason},
            )

        return self.vis_repo.get_by_id(visit_id)

    def get_overdue_records(self) -> List[Dict]:
        """Retrieves all OVERDUE staff sessions and visitor visits formatted for UI display."""
        self.check_and_flag_overdue_records()
        records = []

        recent = {r["id"]: r for r in self.att_repo.get_recent_sessions(limit=500)}
        overdue_staff = self.att_repo.query_sessions(status="OVERDUE")
        for s in overdue_staff:
            name = s.get("full_name") or recent.get(s["id"], {}).get("full_name") or f"Staff #{s['staff_id']}"
            time_in_pht = format_iso_to_pht(s.get("time_in")) if s.get("time_in") else "N/A"
            records.append({
                "id": s["id"],
                "name": name,
                "person_type": "Staff",
                "time_in_pht": time_in_pht,
                "duration": _format_overdue_duration(s.get("time_in")),
                "is_visitor": False,
            })

        overdue_visitors = self.vis_repo.query_visits(status="OVERDUE")
        for v in overdue_visitors:
            time_in_pht = format_iso_to_pht(v.get("time_in")) if v.get("time_in") else "N/A"
            records.append({
                "id": v["id"],
                "name": v.get("visitor_name", "Unknown Visitor"),
                "person_type": "Visitor",
                "time_in_pht": time_in_pht,
                "duration": _format_overdue_duration(v.get("time_in")),
                "is_visitor": True,
            })

        return records

    def force_checkout_log(
        self,
        log_id: int,
        is_visitor: bool,
        admin_id: int,
        reason: str = "Admin Force Check-Out",
    ) -> bool:
        """Forces check-out on an overdue staff session or visitor visit."""
        if is_visitor:
            visit = self.vis_repo.get_by_id(log_id)
            if not visit:
                raise RecordNotFoundError(f"Visitor visit {log_id} not found.")
            self.resolve_visitor_visit(admin_id=admin_id, visit_id=log_id, reason=reason)
            return True
        else:
            session = self.att_repo.get_by_id(log_id)
            if not session:
                raise RecordNotFoundError(f"Attendance session {log_id} not found.")
            self.resolve_staff_session(admin_id=admin_id, session_id=log_id, reason=reason)
            return True