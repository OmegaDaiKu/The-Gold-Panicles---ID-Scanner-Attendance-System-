"""Admin Dashboard Reports and Data Export Tab View."""

import csv
from datetime import datetime, timezone

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.audit_repo import AuditRepository
from src.database.repositories.visitor_repo import VisitorRepository
from src.ui.components.animations import attach_press_feedback
from src.ui.theme import Colors, ObjectNames, Radius, Spacing
from src.utils.icon_helper import IconHelper
from src.utils.time_utils import PHT_TIMEZONE, format_iso_to_pht, get_utc_now_iso


class ReportsView(QWidget):
    """Admin Dashboard Reports and Data Export Tab View."""

    def __init__(self, db_manager=None, reports_service=None, admin_id=None, parent=None, **kwargs):
        super().__init__(parent)
        self.db_manager = db_manager
        self.reports_service = reports_service
        self.admin_id = admin_id
        if db_manager:
            self.att_repo = AttendanceRepository(db_manager)
            self.vis_repo = VisitorRepository(db_manager)
            self.audit_repo = AuditRepository(db_manager)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)

        # Header Card
        header_card = QFrame()
        header_card.setObjectName(ObjectNames.SURFACE_CARD)
        header_card.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px; }}"
        )
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        header_layout.setSpacing(Spacing.XS)

        title_row = QHBoxLayout()
        title_row.setSpacing(Spacing.XS)

        icon_title = QLabel()
        icon_title.setPixmap(IconHelper.get_pixmap("file-text", color=Colors.ACCENT_GOLD, size=18))
        icon_title.setStyleSheet("background: transparent;")
        title_row.addWidget(icon_title)

        title = QLabel("REPORTS & DATA EXPORT")
        title.setObjectName(ObjectNames.SECTION_TITLE)
        title.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 14px; font-weight: 800; letter-spacing: 0.8px; background: transparent;"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        header_layout.addLayout(title_row)

        desc = QLabel("Export publication attendance logs, visitor records, summary statistics, and administrative audit trails to CSV.")
        desc.setObjectName(ObjectNames.TEXT_SECONDARY)
        desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        desc.setWordWrap(True)

        header_layout.addWidget(desc)
        layout.addWidget(header_card)

        # Date Range Filter Card
        filter_card = QFrame()
        filter_card.setObjectName(ObjectNames.SURFACE_CARD)
        filter_card.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px; }}"
        )
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        filter_layout.setSpacing(Spacing.MD)

        lbl_filter_icon = QLabel()
        lbl_filter_icon.setPixmap(IconHelper.get_pixmap("calendar", color=Colors.ACCENT_GOLD, size=16))
        lbl_filter_icon.setStyleSheet("background: transparent;")
        filter_layout.addWidget(lbl_filter_icon)

        lbl_start = QLabel("Start Date:")
        lbl_start.setObjectName(ObjectNames.FORM_LABEL)
        lbl_start.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent;")

        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate().addDays(-7))
        self.date_start.setDisplayFormat("yyyy-MM-dd")

        lbl_end = QLabel("End Date:")
        lbl_end.setObjectName(ObjectNames.FORM_LABEL)
        lbl_end.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-weight: 600; background: transparent;")

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setDisplayFormat("yyyy-MM-dd")

        filter_layout.addWidget(lbl_start)
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(lbl_end)
        filter_layout.addWidget(self.date_end)
        filter_layout.addStretch()

        layout.addWidget(filter_card)

        # Export Grid
        export_grid = QGridLayout()
        export_grid.setSpacing(Spacing.MD)

        export_grid.addWidget(
            self._create_export_card(
                "Staff Attendance Logs",
                "Export complete staff check-in/out records, categories, and resolution notes.",
                "file-text",
                self._export_staff_logs,
            ),
            0,
            0,
        )
        export_grid.addWidget(
            self._create_export_card(
                "Visitor Sign-In Logs",
                "Export guest and visitor log entries, categories, and status history.",
                "users",
                self._export_visitor_logs,
            ),
            0,
            1,
        )
        export_grid.addWidget(
            self._create_export_card(
                "Monthly Summary Report",
                "Generate aggregate duty session statistics and designation breakdowns per staffer.",
                "bar-chart-3",
                self._export_summary_report,
            ),
            1,
            0,
        )
        export_grid.addWidget(
            self._create_export_card(
                "Audit Trail Logs",
                "Export administrative activity, overrides, backups, and security log history.",
                "shield-check",
                self._export_audit_logs,
            ),
            1,
            1,
        )

        layout.addLayout(export_grid)
        layout.addStretch()

    def _create_export_card(self, title: str, description: str, icon_name: str, export_callback) -> QFrame:
        card = QFrame()
        card.setObjectName(ObjectNames.SURFACE_CARD)
        card.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.SM)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(Spacing.XS)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(IconHelper.get_pixmap(icon_name, color=Colors.ACCENT_GOLD, size=20))
        icon_lbl.setStyleSheet("background: transparent;")

        lbl_title = QLabel(title)
        lbl_title.setObjectName(ObjectNames.HEADING_SECTION)
        lbl_title.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 13px; font-weight: 700; background: transparent;"
        )

        top_layout.addWidget(icon_lbl)
        top_layout.addWidget(lbl_title)
        top_layout.addStretch()

        lbl_desc = QLabel(description)
        lbl_desc.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_desc.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; background: transparent;")
        lbl_desc.setWordWrap(True)

        btn_export = QPushButton(" Export to CSV")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_export.setIcon(IconHelper.get_icon("download", color=Colors.BACKGROUND, size=14))
        btn_export.setIconSize(QSize(14, 14))
        btn_export.clicked.connect(export_callback)
        attach_press_feedback(btn_export)

        layout.addLayout(top_layout)
        layout.addWidget(lbl_desc)
        layout.addSpacing(Spacing.XS)
        layout.addWidget(btn_export, alignment=Qt.AlignmentFlag.AlignRight)

        return card

    def _get_save_path(self, default_name: str) -> str:
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Report to CSV", default_name, "CSV Files (*.csv)")
        return filepath

    def _get_selected_date_range_pht(self):
        start_qdate = self.date_start.date()
        end_qdate = self.date_end.date()
        start_dt = datetime(
            start_qdate.year(), start_qdate.month(), start_qdate.day(),
            0, 0, 0, 0, tzinfo=PHT_TIMEZONE
        )
        end_dt = datetime(
            end_qdate.year(), end_qdate.month(), end_qdate.day(),
            23, 59, 59, 999999, tzinfo=PHT_TIMEZONE
        )
        return start_dt, end_dt

    def _parse_iso_to_pht(self, iso_str):
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(PHT_TIMEZONE)
        except (ValueError, TypeError, AttributeError):
            return None

    def _iso_in_range(self, iso_str, start_dt, end_dt) -> bool:
        dt_pht = self._parse_iso_to_pht(iso_str)
        if dt_pht is None:
            return False
        return start_dt <= dt_pht <= end_dt

    @staticmethod
    def _csv_safe(value) -> str:
        if value is None:
            return ""
        text = str(value)
        if text and text[0] in ("=", "+", "-", "@"):
            return "'" + text
        return text

    def _log_export_audit(self, entity_type: str, reason: str, new_values: dict) -> None:
        try:
            self.audit_repo.log_action(
                admin_id=self.admin_id,
                action_type="EXPORT",
                entity_type=entity_type,
                entity_id=0,
                reason=reason,
                old_values=None,
                new_values=new_values,
                timestamp=get_utc_now_iso(),
            )
            return True
        except Exception:
            return False

    def _export_staff_logs(self):
        if not self.db_manager:
            return
        filepath = self._get_save_path("tgp_staff_attendance_logs.csv")
        if not filepath:
            return

        try:
            start_dt, end_dt = self._get_selected_date_range_pht()
            all_sessions = self.att_repo.get_recent_sessions(limit=None)
            sessions = [s for s in all_sessions if self._iso_in_range(s.get("time_in"), start_dt, end_dt)]

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID", "Student ID", "Full Name", "Designation",
                    "Category", "Status", "Time In (PHT)", "Time Out (PHT)", "Resolution Notes"
                ])
                for s in sessions:
                    writer.writerow([
                        self._csv_safe(s.get("id")),
                        self._csv_safe(s.get("student_id_no", "")),
                        self._csv_safe(s.get("full_name", "")),
                        self._csv_safe(s.get("designation", "")),
                        self._csv_safe(s.get("category", "")),
                        self._csv_safe(s.get("status", "")),
                        self._csv_safe(format_iso_to_pht(s.get("time_in"))),
                        self._csv_safe(format_iso_to_pht(s.get("time_out")) if s.get("time_out") else "—"),
                        self._csv_safe(s.get("resolution_notes", "") or ""),
                    ])

            msg = f"Exported {len(sessions)} staff attendance records to:\n{filepath}"

            audit_ok = self._log_export_audit(
                entity_type="staff_attendance_export",
                reason=f"Exported {len(sessions)} staff attendance record(s) to CSV for range "
                       f"{start_dt.date().isoformat()} to {end_dt.date().isoformat()}.",
                new_values={"filepath": filepath, "record_count": len(sessions)},
            )
            if not audit_ok:
                msg += "\n\n(Note: this export could not be recorded in the audit trail.)"

            QMessageBox.information(self, "Export Successful", msg)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _export_visitor_logs(self):
        if not self.db_manager:
            return
        filepath = self._get_save_path("tgp_visitor_visits.csv")
        if not filepath:
            return

        try:
            start_dt, end_dt = self._get_selected_date_range_pht()
            all_visits = self.vis_repo.query_visits()
            visits = [v for v in all_visits if self._iso_in_range(v.get("time_in"), start_dt, end_dt)]

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID", "Student ID", "Visitor Name", "Category",
                    "Status", "Time In (PHT)", "Time Out (PHT)", "Resolution Notes"
                ])
                for v in visits:
                    writer.writerow([
                        self._csv_safe(v.get("id")),
                        self._csv_safe(v.get("student_id_no", "")),
                        self._csv_safe(v.get("visitor_name", "")),
                        self._csv_safe(v.get("category", "Visit")),
                        self._csv_safe(v.get("status", "")),
                        self._csv_safe(format_iso_to_pht(v.get("time_in"))),
                        self._csv_safe(format_iso_to_pht(v.get("time_out")) if v.get("time_out") else "—"),
                        self._csv_safe(v.get("resolution_notes", "") or ""),
                    ])

            msg = f"Exported {len(visits)} visitor records to:\n{filepath}"

            audit_ok = self._log_export_audit(
                entity_type="visitor_logs_export",
                reason=f"Exported {len(visits)} visitor record(s) to CSV for range "
                       f"{start_dt.date().isoformat()} to {end_dt.date().isoformat()}.",
                new_values={"filepath": filepath, "record_count": len(visits)},
            )
            if not audit_ok:
                msg += "\n\n(Note: this export could not be recorded in the audit trail.)"

            QMessageBox.information(self, "Export Successful", msg)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _export_summary_report(self):
        if not self.db_manager:
            return
        filepath = self._get_save_path("tgp_attendance_summary.csv")
        if not filepath:
            return

        try:
            start_dt, end_dt = self._get_selected_date_range_pht()
            start_utc = start_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            end_utc = end_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            conn = self.db_manager.get_connection()

            cursor = conn.execute("PRAGMA table_info(staff)")
            staff_cols = [str(row[1]) for row in cursor.fetchall()]
            sid_col = "student_id_no" if "student_id_no" in staff_cols else ("staff_id" if "staff_id" in staff_cols else "id")

            query = f"""
                SELECT 
                    s.student_id_no,
                    s.full_name,
                    s.designation,
                    COUNT(a.id) as total_sessions,
                    SUM(CASE WHEN a.category = 'Duty' THEN 1 ELSE 0 END) as duty_sessions,
                    SUM(CASE WHEN a.category = 'Visit' THEN 1 ELSE 0 END) as visit_sessions,
                    SUM(CASE WHEN a.status = 'OVERDUE' THEN 1 ELSE 0 END) as overdue_sessions
                FROM staff s
                LEFT JOIN attendance_sessions a
                    ON (a.staff_id = s.id OR a.staff_id = s.{sid_col})
                    AND datetime(a.time_in) BETWEEN datetime(?) AND datetime(?)
                GROUP BY s.id
                ORDER BY s.full_name ASC
            """
            cursor = conn.execute(query, (start_utc, end_utc))
            rows = cursor.fetchall()

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Student ID", "Full Name", "Designation",
                    "Total Sessions", "Duty Sessions", "Visit Sessions", "Overdue Sessions"
                ])
                for r in rows:
                    writer.writerow([self._csv_safe(v) for v in r])

            msg = f"Exported summary report for {len(rows)} staff members to:\n{filepath}"

            audit_ok = self._log_export_audit(
                entity_type="summary_report_export",
                reason=f"Exported attendance summary report for {len(rows)} staff member(s), range "
                       f"{start_dt.date().isoformat()} to {end_dt.date().isoformat()}.",
                new_values={"filepath": filepath, "staff_count": len(rows)},
            )
            if not audit_ok:
                msg += "\n\n(Note: this export could not be recorded in the audit trail.)"

            QMessageBox.information(self, "Export Successful", msg)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _export_audit_logs(self):
        if not self.db_manager:
            return
        filepath = self._get_save_path("tgp_audit_trail_logs.csv")
        if not filepath:
            return

        try:
            start_dt, end_dt = self._get_selected_date_range_pht()
            all_logs = self.audit_repo.list_logs(limit=None)
            logs = [item for item in all_logs if self._iso_in_range(item.get("timestamp"), start_dt, end_dt)]

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID", "Admin Username", "Action", "Entity Type",
                    "Entity ID", "Reason", "Timestamp (PHT)"
                ])
                for item in logs:
                    writer.writerow([
                        self._csv_safe(item.get("id")),
                        self._csv_safe(item.get("admin_username") or f"Admin #{item.get('admin_id')}"),
                        self._csv_safe(item.get("action_type", "")),
                        self._csv_safe(item.get("entity_type", "")),
                        self._csv_safe(item.get("entity_id", "")),
                        self._csv_safe(item.get("reason", "")),
                        self._csv_safe(format_iso_to_pht(item.get("timestamp"))),
                    ])

            msg = f"Exported {len(logs)} audit trail entries to:\n{filepath}"
            QMessageBox.information(self, "Export Successful", msg)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))


ReportsExportsTab = ReportsView
ReportsTab = ReportsView