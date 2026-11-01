""""Core business logic for time-in, time-out, and live attendance board feed management."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Set
from src.core.constants import AttendanceCategory
from src.core.exceptions import InvalidStateError
from src.database.connection import DatabaseConnectionManager
from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.staff_repo import StaffRepository
from src.database.repositories.visitor_repo import VisitorRepository
from src.services.audit_service import AuditService
from src.utils.time_utils import PHT_TIMEZONE, format_iso_to_pht, get_utc_now_iso
from src.utils.validators import extract_student_id_from_payload, sanitize_student_id, validate_person_name

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = ("OPEN", "OVERDUE")
TIME_OUT_COOLDOWN_SECONDS = 10
OVERDUE_AUTO_RESOLVE_GRACE_HOURS = 72


def _parse_iso_to_utc_datetime(iso_timestamp: str) -> datetime:
    """Parses an ISO-8601 timestamp string into a timezone-aware UTC datetime."""
    value = iso_timestamp
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _seconds_since_time_in(time_in_iso: str) -> float:
    """Returns elapsed seconds between `time_in_iso` and current time (UTC)."""
    try:
        time_in_dt = _parse_iso_to_utc_datetime(time_in_iso)
        now_dt = datetime.now(timezone.utc)
        return (now_dt - time_in_dt).total_seconds()
    except Exception:
        logger.warning(
            "Could not parse time_in timestamp '%s' for cooldown check -- "
            "treating cooldown as already expired.",
            time_in_iso,
        )
        return float("inf")


def _matches_pht_date(time_in_iso: Optional[str], target_date_str: str) -> bool:
    """Returns True if `time_in_iso` falls on `target_date_str` in PHT."""
    if not time_in_iso:
        return False
    try:
        dt_utc = _parse_iso_to_utc_datetime(time_in_iso)
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except Exception:
        logger.warning(
            "Could not compare time_in timestamp '%s' against target date "
            "'%s' for PHT day-match check.",
            time_in_iso, target_date_str,
        )
        return False
    return dt_utc.astimezone(PHT_TIMEZONE).date() == target_date


def _is_today_pht(time_in_iso: Optional[str]) -> bool:
    """Returns True if `time_in_iso` falls on today's calendar date in PHT."""
    today_pht_str = datetime.now(PHT_TIMEZONE).date().isoformat()
    return _matches_pht_date(time_in_iso, today_pht_str)


class AttendanceService:
    """Handles attendance session lifecycle evaluation."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager
        self.att_repo = AttendanceRepository(db_manager)
        self.staff_repo = StaffRepository(db_manager)
        self.visitor_repo = VisitorRepository(db_manager)
        self.audit_service = AuditService(db_manager)

    def _log_auto_resolve_audit(self, entity_type: str, record: Dict, reason: Optional[str] = None) -> None:
        """Writes an audit log entry for a system auto-resolved session or visit."""
        if reason is None:
            reason = (
                f"Automatic system resolution after "
                f"{OVERDUE_AUTO_RESOLVE_GRACE_HOURS}h grace period "
                f"exceeded (time_in-based)."
            )
        try:
            self.audit_service.log_action(
                admin_id=None,
                action_type="AUTO_RESOLVE_OVERDUE",
                entity_type=entity_type,
                entity_id=record["id"],
                reason=reason,
                old_values=record.get("old_values"),
                new_values=record.get("new_values"),
            )
        except Exception:
            logger.warning(
                "Failed to write audit log entry for auto-resolved %s id=%s.",
                entity_type, record.get("id"),
                exc_info=True,
            )

    def _refresh_overdue_flags(self) -> None:
        """Runs the OVERDUE-flagging sweep and 72-hour auto-resolve backstop.

        NOTE (flagged, not changed this pass): this is invoked unconditionally
        at the top of evaluate_scanned_id() -- i.e. on every hardware QR scan
        -- as well as independently from get_live_attendance_board_feed(),
        get_attendance_board_feed_for_date(), and get_quick_stats(). This
        matches the external audit's H4 finding: the sweep runs synchronously
        on the scan hot path rather than on a timer. Left unchanged pending a
        decision on whether to move this to the existing 30s board-refresh
        cadence instead, since that touches the scan call site in
        station_view.py which hasn't been reviewed this session.
        """
        self.att_repo.flag_overdue_sessions()
        resolved_sessions = self.att_repo.auto_resolve_stale_overdue_sessions(
            grace_hours=OVERDUE_AUTO_RESOLVE_GRACE_HOURS
        )
        for record in resolved_sessions:
            self._log_auto_resolve_audit("attendance_session", record)

        self.visitor_repo.flag_overdue_visits()
        resolved_visits = self.visitor_repo.auto_resolve_stale_overdue_visits(
            grace_hours=OVERDUE_AUTO_RESOLVE_GRACE_HOURS
        )
        for record in resolved_visits:
            self._log_auto_resolve_audit("visitor_visit", record)

    def evaluate_scanned_id(self, scanned_id: str) -> Dict:
        """Evaluates scanned Student ID to determine appropriate kiosk action."""
        self._refresh_overdue_flags()

        extracted_id, _ = extract_student_id_from_payload(scanned_id)
        clean_id = extracted_id if extracted_id else (scanned_id.strip() if scanned_id else "")

        staff = self.staff_repo.get_by_student_id(clean_id)

        if staff:
            active_session = self._find_active_staff_session(staff["id"])

            if active_session:
                status = active_session.get("status")

                if status == "OVERDUE":
                    return {
                        "type": "STAFF_OVERDUE_LOCKED",
                        "action": "OVERDUE_LOCKED",
                        "staff": staff,
                        "open_session": active_session,
                        "message": (
                            f"{staff['full_name']}'s attendance session is overdue and "
                            f"requires administrator resolution. Please see the front desk."
                        ),
                        "student_id_no": clean_id,
                    }

                elapsed = _seconds_since_time_in(active_session["time_in"])

                if elapsed < TIME_OUT_COOLDOWN_SECONDS:
                    remaining = max(1, round(TIME_OUT_COOLDOWN_SECONDS - elapsed))
                    return {
                        "type": "STAFF_TIME_OUT_COOLDOWN",
                        "action": "TIME_OUT_COOLDOWN",
                        "staff": staff,
                        "open_session": active_session,
                        "seconds_remaining": remaining,
                        "student_id_no": clean_id,
                    }

                formatted_time = format_iso_to_pht(active_session["time_in"])
                return {
                    "type": "STAFF_TIME_OUT_READY",
                    "action": "TIME_OUT",
                    "staff": staff,
                    "open_session": active_session,
                    "formatted_time_in": formatted_time,
                    "student_id_no": clean_id,
                }

            is_active = staff.get("is_active", staff.get("active", 1))
            if not is_active:
                return {
                    "type": "INACTIVE_STAFF",
                    "action": "INACTIVE_STAFF",
                    "message": f"Staff account for {staff['full_name']} ({clean_id}) is deactivated. Please see an administrator.",
                    "student_id_no": clean_id,
                }

            # Fallback block: No active session exists, proceed to authorize Time-In
            return {
                "type": "STAFF_TIME_IN_READY",
                "action": "TIME_IN",
                "staff": staff,
                "student_id_no": clean_id,
            }

        active_visit = self._find_active_visitor_visit(clean_id)

        if active_visit:
            status = active_visit.get("status")

            if status == "OVERDUE":
                return {
                    "type": "VISITOR_OVERDUE_LOCKED",
                    "action": "OVERDUE_LOCKED",
                    "open_visit": active_visit,
                    "message": (
                        f"{active_visit.get('visitor_name', 'This visitor')}'s visit is "
                        f"overdue and requires administrator resolution. Please see the "
                        f"front desk."
                    ),
                    "student_id_no": clean_id,
                }

            elapsed = _seconds_since_time_in(active_visit["time_in"])

            if elapsed < TIME_OUT_COOLDOWN_SECONDS:
                remaining = max(1, round(TIME_OUT_COOLDOWN_SECONDS - elapsed))
                return {
                    "type": "VISITOR_TIME_OUT_COOLDOWN",
                    "action": "TIME_OUT_COOLDOWN",
                    "open_visit": active_visit,
                    "seconds_remaining": remaining,
                    "student_id_no": clean_id,
                }

            formatted_time = format_iso_to_pht(active_visit["time_in"])
            return {
                "type": "VISITOR_TIME_OUT_READY",
                "action": "TIME_OUT",
                "open_visit": active_visit,
                "formatted_time_in": formatted_time,
                "student_id_no": clean_id,
            }

        return {
            "type": "GUEST_VISITOR_NEW",
            "action": "VISITOR_TIME_IN",
            "student_id_no": clean_id,
            "staff": None,
            "open_session": None,
        }

    def _find_active_staff_session(self, staff_id: int) -> Optional[Dict]:
        """Returns staff member's current OPEN session or SAME-DAY OVERDUE session."""
        for status in _ACTIVE_STATUSES:
            sessions = self.att_repo.query_sessions(staff_id=staff_id, status=status)
            if sessions:
                session = sessions[0]
                if status == "OVERDUE" and not _is_today_pht(session.get("time_in")):
                    continue
                return session
        return None

    def _find_active_visitor_visit(self, student_id_no: str) -> Optional[Dict]:
        """Returns current OPEN visit or SAME-DAY OVERDUE visit for given student ID."""
        active_visit = self.visitor_repo.get_open_visit_by_student_id(student_id_no)
        if active_visit:
            return active_visit

        overdue_visits = self.visitor_repo.query_visits(status="OVERDUE")
        for v in overdue_visits:
            if v.get("student_id_no") == student_id_no:
                if not _is_today_pht(v.get("time_in")):
                    continue
                return v
        return None

    def confirm_staff_time_in(self, staff_id: int, category: Union[str, AttendanceCategory] = "Duty") -> Dict:
        """Confirms and commits a staff Time-In session."""
        existing = self._find_active_staff_session(staff_id)
        if existing:
            logger.warning(
                "confirm_staff_time_in: staff_id=%s already has active session (id=%s, status=%s).",
                staff_id, existing.get("id"), existing.get("status"),
            )
            return existing

        cat_str = category.value if hasattr(category, "value") else str(category)
        session_id = self.att_repo.create_session(staff_id=staff_id, category=cat_str, status="OPEN")
        return self.att_repo.get_by_id(session_id)

    def confirm_staff_time_out(self, session_id: int) -> Dict:
        """Confirms and commits a staff Time-Out session.

        FIXED THIS SESSION: previously this discarded close_session()'s
        return value entirely and just returned get_by_id() regardless of
        whether the close actually applied. Now logs a warning (not a raised
        exception -- deliberately, to avoid introducing a new uncaught
        exception path on the kiosk scan flow without having reviewed how
        station_view.py calls this) when the underlying row was not in
        OPEN/OVERDUE at the time of the call, so a no-op is at least visible
        in logs instead of silently presenting as a successful time-out.
        """
        now_iso = get_utc_now_iso()
        closed = self.att_repo.close_session(session_id=session_id, time_out=now_iso)
        current = self.att_repo.get_by_id(session_id)
        if not closed:
            logger.warning(
                "confirm_staff_time_out: close_session(session_id=%s) was a no-op "
                "-- record status is now '%s'. The returned record reflects its "
                "existing state, not a fresh time-out.",
                session_id, current.get("status") if current else "NOT FOUND",
            )
        return current

    def confirm_visitor_time_in(self, student_id_no: str, visitor_name: str) -> Dict:
        """Confirms and commits a guest visitor Time-In visit."""
        clean_sid = sanitize_student_id(student_id_no) if student_id_no else student_id_no

        existing = self._find_active_visitor_visit(clean_sid)
        if existing:
            logger.warning(
                "confirm_visitor_time_in: student_id_no=%s already has active visit (id=%s, status=%s).",
                clean_sid, existing.get("id"), existing.get("status"),
            )
            return existing

        clean_name = validate_person_name(visitor_name) if visitor_name else visitor_name
        now_iso = get_utc_now_iso()
        visit_id = self.visitor_repo.create_visit(
            student_id_no=clean_sid,
            visitor_name=clean_name,
            time_in=now_iso,
            category="Visit",
        )
        return self.visitor_repo.get_by_id(visit_id)

    def confirm_visitor_time_out(self, visit_id: int) -> Dict:
        """Confirms and commits a guest visitor Time-Out visit.

        FIXED THIS SESSION: same change as confirm_staff_time_out() above --
        close_visit()'s return value is now checked and a no-op is logged
        instead of silently discarded.
        """
        now_iso = get_utc_now_iso()
        closed = self.visitor_repo.close_visit(visit_id=visit_id, time_out=now_iso)
        current = self.visitor_repo.get_by_id(visit_id)
        if not closed:
            logger.warning(
                "confirm_visitor_time_out: close_visit(visit_id=%s) was a no-op "
                "-- record status is now '%s'. The returned record reflects its "
                "existing state, not a fresh time-out.",
                visit_id, current.get("status") if current else "NOT FOUND",
            )
        return current

    @staticmethod
    def _staff_session_to_feed_row(s: Dict) -> Dict:
        """Shapes a raw staff attendance row into standard UI board format."""
        return {
            "student_id_no": s.get("student_id_no") or "",
            "full_name": s.get("full_name") or "Unknown",
            "designation": s.get("designation") or "",
            "category": s.get("category") or "",
            "status": s.get("status") or "",
            "type": "STAFF",
            "time_in": s.get("time_in"),
            "time_out": s.get("time_out"),
            "time_in_display": format_iso_to_pht(s.get("time_in")),
            "time_out_display": format_iso_to_pht(s.get("time_out")),
        }

    @staticmethod
    def _visitor_visit_to_feed_row(v: Dict) -> Dict:
        """Shapes a raw visitor visit row into standard UI board format."""
        return {
            "student_id_no": v.get("student_id_no") or "",
            "full_name": v.get("visitor_name") or "Unknown",
            "designation": "Guest Visitor",
            "category": v.get("category") or "Visit",
            "status": v.get("status") or "",
            "type": "VISITOR",
            "time_in": v.get("time_in"),
            "time_out": v.get("time_out"),
            "time_in_display": format_iso_to_pht(v.get("time_in")),
            "time_out_display": format_iso_to_pht(v.get("time_out")),
        }

    def get_live_attendance_feed(self, limit: int = 50) -> List[Dict]:
        """Retrieves recent attendance records for UI rendering across history."""
        staff_sessions = self.att_repo.get_recent_sessions(limit=limit)
        visitor_visits = self.visitor_repo.query_visits(limit=limit)

        feed = [self._staff_session_to_feed_row(s) for s in staff_sessions]
        feed.extend(self._visitor_visit_to_feed_row(v) for v in visitor_visits)

        feed.sort(key=lambda x: x.get("time_in") or "", reverse=True)
        return feed[:limit]

    def get_live_attendance_board_feed(self, limit: int = 50) -> List[Dict]:
        """Returns live attendance feed filtered to today's PHT calendar entries."""
        self._refresh_overdue_flags()
        full_feed = self.get_live_attendance_feed(limit=limit)
        return [item for item in full_feed if _is_today_pht(item.get("time_in"))]

    def get_attendance_board_feed_for_date(self, date_str: str, limit: Optional[int] = None) -> List[Dict]:
        """Returns attendance board rows for a specified PHT calendar date."""
        self._refresh_overdue_flags()

        staff_sessions = self.att_repo.query_sessions(date=date_str, limit=limit)
        feed = [self._staff_session_to_feed_row(s) for s in staff_sessions]

        visitor_visits = self.visitor_repo.query_visits(date=date_str, limit=limit)
        feed.extend(self._visitor_visit_to_feed_row(v) for v in visitor_visits)

        feed.sort(key=lambda x: x.get("time_in") or "", reverse=True)
        return feed

    def get_dates_with_attendance_records(self) -> Set[str]:
        """Returns the set of PHT calendar date strings with existing records."""
        staff_dates = self.att_repo.get_distinct_session_dates()
        visitor_dates = self.visitor_repo.get_distinct_visit_dates()
        return set(staff_dates) | set(visitor_dates)

    def get_quick_stats(self) -> Dict[str, int]:
        """Returns active duty staff and visitor headcount counts."""
        self._refresh_overdue_flags()

        open_sessions = self.att_repo.query_sessions(status="OPEN")
        active_duty = sum(
            1 for s in open_sessions
            if str(s.get("category", "")).upper() == "DUTY"
        )
        open_visits = self.visitor_repo.query_visits(status="OPEN")
        active_visitors = len(open_visits)

        return {
            "active_duty_staff": active_duty,
            "active_visitors": active_visitors,
        }