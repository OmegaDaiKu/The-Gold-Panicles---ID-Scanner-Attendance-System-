""""Attendance Logs Review Tab with full CRUD: search, filter, manual create, edit, and delete."""

from datetime import date, datetime, timezone

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.database.connection import DatabaseConnectionManager
from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.audit_repo import AuditRepository
from src.database.repositories.staff_repo import StaffRepository
from src.database.repositories.visitor_repo import VisitorRepository
from src.ui.theme import Colors, ObjectNames
from src.utils.time_utils import PHT_TIMEZONE, format_iso_to_pht, get_utc_now_iso


class AttendanceLogsTab(QWidget):
    """Historical attendance records table view with full CRUD capabilities."""

    HEADERS = ["#", "Date", "Time In", "Time Out", "Student ID No", "Full Name", "Designation", "Category", "Status", "Actions"]

    def __init__(self, db_manager: DatabaseConnectionManager, admin_id: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager

        if admin_id is None:
            raise ValueError(
                "AttendanceLogsTab requires a valid 'admin_id' for audit-trail attribution. "
                "Received: {!r}".format(admin_id)
            )
        self.admin_id = admin_id

        self.att_repo = AttendanceRepository(db_manager)
        self.staff_repo = StaffRepository(db_manager)
        self.vis_repo = VisitorRepository(db_manager)
        self.audit_repo = AuditRepository(db_manager)
        self._all_records = []
        self._selected_date_filter: date | None = None

        self._init_ui()
        self.refresh_logs()

    def _log_action(self, action_type: str, entity_type: str, entity_id, reason: str,
                     old_values: dict | None, new_values: dict | None) -> bool:
        try:
            self.audit_repo.log_action(
                admin_id=self.admin_id,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id if isinstance(entity_id, int) else 0,
                reason=reason,
                old_values=old_values,
                new_values=new_values,
                timestamp=get_utc_now_iso(),
            )
            return True
        except Exception:
            return False

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        lbl_title = QLabel("STAFF & VISITOR ATTENDANCE LOGS")
        lbl_title.setObjectName(ObjectNames.SECTION_TITLE)
        title_row.addWidget(lbl_title)
        title_row.addStretch()

        btn_manual = QPushButton("+ MANUAL LOG ENTRY")
        btn_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_manual.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_manual.clicked.connect(self._show_create_dialog)
        title_row.addWidget(btn_manual)

        layout.addLayout(title_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍  Search by Student ID, Name, or Designation...")
        self.txt_search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.txt_search, stretch=3)

        self.cmb_type_filter = QComboBox()
        self.cmb_type_filter.addItems(["All Types", "Staff", "Visitor"])
        self.cmb_type_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.cmb_type_filter, stretch=1)

        self.cmb_category_filter = QComboBox()
        self.cmb_category_filter.addItems(["All Categories", "Duty", "Visit"])
        self.cmb_category_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.cmb_category_filter, stretch=1)

        self.cmb_status_filter = QComboBox()
        self.cmb_status_filter.addItems(["All Status", "OPEN", "COMPLETED", "OVERDUE", "RESOLVED"])
        self.cmb_status_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.cmb_status_filter, stretch=1)

        self.btn_date_filter = QPushButton("📅  Filter by Date")
        self.btn_date_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_date_filter.setObjectName(ObjectNames.BTN_CHROME)
        self.btn_date_filter.clicked.connect(self._open_date_filter_dialog)
        filter_row.addWidget(self.btn_date_filter)

        self.btn_clear_date_filter = QPushButton("✕")
        self.btn_clear_date_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_date_filter.setToolTip("Clear date filter")
        self.btn_clear_date_filter.setFixedWidth(28)
        self.btn_clear_date_filter.setObjectName(ObjectNames.BTN_ROW_DELETE)
        self.btn_clear_date_filter.clicked.connect(self._clear_date_filter)
        self.btn_clear_date_filter.setVisible(False)
        filter_row.addWidget(self.btn_clear_date_filter)

        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(9, 190)

        layout.addWidget(self.table)

        self.lbl_count = QLabel("0 records")
        self.lbl_count.setObjectName(ObjectNames.TEXT_MUTED)
        layout.addWidget(self.lbl_count)

    def refresh_logs(self) -> None:
        staff_records = self.att_repo.get_recent_sessions(limit=5000)
        for r in staff_records:
            r["is_visitor"] = False

        visitor_rows = self.vis_repo.query_visits()
        visitor_records = []
        for v in visitor_rows:
            visitor_records.append({
                "id": v.get("id"),
                "is_visitor": True,
                "student_id_no": v.get("student_id_no", ""),
                "full_name": v.get("visitor_name") or "Unknown Visitor",
                "designation": "Visitor",
                "category": v.get("category", ""),
                "status": v.get("status", ""),
                "time_in": v.get("time_in"),
                "time_out": v.get("time_out"),
                "resolution_notes": v.get("resolution_notes"),
            })

        combined = staff_records + visitor_records
        combined.sort(key=lambda r: str(r.get("time_in") or ""), reverse=True)

        self._all_records = combined
        self._apply_filter()

    @staticmethod
    def _iso_to_pht_date(iso_str) -> date | None:
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(PHT_TIMEZONE).date()
        except (ValueError, TypeError, AttributeError):
            return None

    def _get_valid_log_dates(self) -> set:
        valid = set()
        for r in self._all_records:
            d = self._iso_to_pht_date(r.get("time_in"))
            if d is not None:
                valid.add(d)
        return valid

    def _open_date_filter_dialog(self) -> None:
        valid_dates = self._get_valid_log_dates()
        dialog = _DateFilterDialog(valid_dates=valid_dates, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.clear_filter:
                self._clear_date_filter()
            elif dialog.result_date is not None:
                self._selected_date_filter = dialog.result_date
                self.btn_date_filter.setText(f"📅  {dialog.result_date.strftime('%b %d, %Y')}")
                self.btn_clear_date_filter.setVisible(True)
                self._apply_filter()

    def _clear_date_filter(self) -> None:
        self._selected_date_filter = None
        self.btn_date_filter.setText("📅  Filter by Date")
        self.btn_clear_date_filter.setVisible(False)
        self._apply_filter()

    def _apply_filter(self) -> None:
        search_text = self.txt_search.text().strip().lower()
        type_filter = self.cmb_type_filter.currentText()
        cat_filter = self.cmb_category_filter.currentText()
        status_filter = self.cmb_status_filter.currentText()

        filtered = []
        for item in self._all_records:
            is_visitor = bool(item.get("is_visitor"))
            if type_filter == "Staff" and is_visitor:
                continue
            if type_filter == "Visitor" and not is_visitor:
                continue
            if cat_filter != "All Categories" and (item.get("category") or "") != cat_filter:
                continue
            if status_filter != "All Status" and (item.get("status") or "") != status_filter:
                continue
            if self._selected_date_filter is not None:
                item_date = self._iso_to_pht_date(item.get("time_in"))
                if item_date != self._selected_date_filter:
                    continue
            if search_text:
                haystack = f"{item.get('student_id_no', '')} {item.get('full_name', '')} {item.get('designation', '')}".lower()
                if search_text not in haystack:
                    continue
            filtered.append(item)

        self._render_rows(filtered)
        self.lbl_count.setText(f"{len(filtered)} of {len(self._all_records)} records")

    def _render_rows(self, records: list) -> None:
        self.table.setRowCount(0)

        STATUS_COLORS = {
            "OPEN": Colors.STATUS_OPEN,
            "COMPLETED": Colors.STATUS_COMPLETED,
            "OVERDUE": Colors.STATUS_OVERDUE,
            "RESOLVED": Colors.STATUS_RESOLVED,
        }

        for idx, item in enumerate(records, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            pht_date = self._iso_to_pht_date(item.get("time_in"))
            date_str = pht_date.strftime("%b %d, %Y") if pht_date else "—"

            items = [
                QTableWidgetItem(str(idx)),
                QTableWidgetItem(date_str),
                QTableWidgetItem(format_iso_to_pht(item.get("time_in"))),
                QTableWidgetItem(format_iso_to_pht(item.get("time_out"))),
                QTableWidgetItem(item.get("student_id_no", "")),
                QTableWidgetItem(item.get("full_name", "")),
                QTableWidgetItem(item.get("designation", "")),
                QTableWidgetItem(item.get("category", "")),
                QTableWidgetItem(item.get("status", "")),
            ]

            if item.get("is_visitor"):
                items[6].setForeground(QColor(Colors.TEXT_MUTED))
            else:
                items[6].setForeground(QColor(Colors.ACCENT_GOLD))

            status_text = item.get("status", "")
            items[8].setForeground(QColor(STATUS_COLORS.get(status_text, Colors.TEXT_MUTED)))

            for col_idx, table_item in enumerate(items):
                table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, col_idx, table_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            btn_edit = QPushButton("EDIT")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.setObjectName(ObjectNames.BTN_ROW_EDIT)
            btn_edit.clicked.connect(lambda _, r=item: self._show_edit_dialog(r))

            btn_delete = QPushButton("DELETE")
            btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_delete.setObjectName(ObjectNames.BTN_ROW_DELETE)
            btn_delete.clicked.connect(lambda _, r=item: self._handle_delete(r))

            actions_layout.addWidget(btn_edit)
            actions_layout.addWidget(btn_delete)
            self.table.setCellWidget(row_idx, 9, actions_widget)

    def _show_create_dialog(self) -> None:
        dialog = _AttendanceFormDialog(
            db_manager=self.db_manager,
            parent=self,
            mode="create",
            admin_id=self.admin_id,
            audit_repo=self.audit_repo,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_logs()

    def _show_edit_dialog(self, record: dict) -> None:
        dialog = _AttendanceFormDialog(
            db_manager=self.db_manager,
            parent=self,
            mode="edit",
            record=record,
            admin_id=self.admin_id,
            audit_repo=self.audit_repo,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_logs()

    def _handle_delete(self, record: dict) -> None:
        is_visitor = bool(record.get("is_visitor"))
        record_kind = "Visitor" if is_visitor else "Staff"
        name = record.get("full_name", "Unknown")
        time_in = format_iso_to_pht(record.get("time_in"))

        reply = QMessageBox.warning(
            self,
            "Confirm Deletion",
            f"Permanently delete the {record_kind.lower()} attendance record for:\n\n"
            f"  {name}\n  Time In: {time_in}\n  Status: {record.get('status', '')}\n\n"
            f"This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if is_visitor:
                    self.vis_repo.delete_visit(record["id"])
                    entity_type = "visitor_visit"
                else:
                    self.att_repo.delete_session(record["id"])
                    entity_type = "attendance_session"

                audit_ok = self._log_action(
                    action_type="DELETE",
                    entity_type=entity_type,
                    entity_id=record.get("id"),
                    reason=f"Permanently deleted {record_kind.lower()} attendance record for "
                           f"'{name}' (Time In: {time_in}, Status: {record.get('status', '')}).",
                    old_values={
                        "student_id_no": record.get("student_id_no", ""),
                        "full_name": name,
                        "category": record.get("category", ""),
                        "status": record.get("status", ""),
                        "time_in": record.get("time_in"),
                        "time_out": record.get("time_out"),
                        "resolution_notes": record.get("resolution_notes"),
                    },
                    new_values=None,
                )

                msg = f"{record_kind} attendance record deleted successfully."
                if not audit_ok:
                    msg += "\n\n(Note: this deletion could not be recorded in the audit trail.)"
                QMessageBox.information(self, "Deleted", msg)
                self.refresh_logs()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


class _LogDateCalendarWidget(QCalendarWidget):
    date_confirmed = Signal(QDate)

    def __init__(self, valid_dates: set, parent=None):
        super().__init__(parent)
        self._valid_dates = valid_dates
        self._last_valid_selection = QDate.currentDate()
        self.setGridVisible(True)
        self.clicked.connect(self._on_date_clicked)

    def _on_date_clicked(self, qdate: QDate) -> None:
        py_date = qdate.toPython()
        if py_date not in self._valid_dates:
            self.setSelectedDate(self._last_valid_selection)
            return
        self._last_valid_selection = qdate
        self.date_confirmed.emit(qdate)

    def paintCell(self, painter, rect, date) -> None:
        super().paintCell(painter, rect, date)
        py_date = date.toPython()
        if py_date not in self._valid_dates:
            painter.save()
            painter.fillRect(rect, QColor(0, 0, 0, 140))
            painter.restore()


class _DateFilterDialog(QDialog):
    def __init__(self, valid_dates: set, parent=None):
        super().__init__(parent)
        self.valid_dates = valid_dates
        self.result_date: date | None = None
        self.clear_filter = False

        self.setWindowTitle("Filter by Date")
        self.setFixedSize(400, 460)
        self.setModal(True)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        lbl_title = QLabel("SELECT A DATE")
        lbl_title.setObjectName(ObjectNames.DIALOG_HEADER_INFO)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_hint = QLabel("Greyed-out dates have no attendance records and cannot be selected.")
        lbl_hint.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_hint.setWordWrap(True)
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_hint)

        self.calendar = _LogDateCalendarWidget(valid_dates=self.valid_dates, parent=self)
        self.calendar.date_confirmed.connect(self._on_date_confirmed)
        layout.addWidget(self.calendar)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_clear = QPushButton("CLEAR FILTER")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setObjectName(ObjectNames.BTN_CHROME)
        btn_clear.clicked.connect(self._on_clear_clicked)

        btn_close = QPushButton("CLOSE")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setObjectName(ObjectNames.BTN_CANCEL)
        btn_close.clicked.connect(self.reject)

        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _on_date_confirmed(self, qdate: QDate) -> None:
        self.result_date = qdate.toPython()
        self.clear_filter = False
        self.accept()

    def _on_clear_clicked(self) -> None:
        self.clear_filter = True
        self.result_date = None
        self.accept()


class _AttendanceFormDialog(QDialog):
    def __init__(self, db_manager, parent=None, mode="create", record=None, admin_id=None, audit_repo=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.att_repo = AttendanceRepository(db_manager)
        self.staff_repo = StaffRepository(db_manager)
        self.vis_repo = VisitorRepository(db_manager)
        self.mode = mode
        self.record = record
        self.admin_id = admin_id
        self.audit_repo = audit_repo
        self.is_visitor = bool(record.get("is_visitor")) if record else False

        title = "EDIT ATTENDANCE RECORD" if mode == "edit" else "MANUAL ATTENDANCE LOG ENTRY"
        self.setWindowTitle(title)
        self.setFixedSize(480, 420)
        self.setModal(True)

        self._init_ui()

    def _log_action(self, action_type: str, entity_type: str, entity_id, reason: str,
                     old_values: dict | None, new_values: dict | None) -> bool:
        if self.audit_repo is None or self.admin_id is None:
            return False
        try:
            self.audit_repo.log_action(
                admin_id=self.admin_id,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=entity_id if isinstance(entity_id, int) else 0,
                reason=reason,
                old_values=old_values,
                new_values=new_values,
                timestamp=get_utc_now_iso(),
            )
            return True
        except Exception:
            return False

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        title_text = "EDIT ATTENDANCE RECORD" if self.mode == "edit" else "CREATE MANUAL LOG ENTRY"
        lbl_title = QLabel(title_text)
        lbl_title.setObjectName(ObjectNames.DIALOG_HEADER_INFO)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        if self.mode == "create":
            self.cmb_staff = QComboBox()
            all_staff = self.staff_repo.list_all(active_only=True)
            for s in all_staff:
                self.cmb_staff.addItem(f"{s['student_id_no']} — {s['full_name']}", s["id"])
            lbl_staff = QLabel("Staff Member:")
            lbl_staff.setObjectName(ObjectNames.FORM_LABEL)
            form_layout.addRow(lbl_staff, self.cmb_staff)
        else:
            lbl_staff_info = QLabel(f"{self.record.get('student_id_no', '')} — {self.record.get('full_name', '')}")
            lbl_staff_info.setObjectName(ObjectNames.INFO_CHIP_GOLD)
            lbl_staff_label = QLabel("Visitor:" if self.is_visitor else "Staff:")
            lbl_staff_label.setObjectName(ObjectNames.FORM_LABEL)
            form_layout.addRow(lbl_staff_label, lbl_staff_info)

        self.cmb_category = QComboBox()
        self.cmb_category.addItems(["Duty", "Visit"])
        lbl_cat = QLabel("Category:")
        lbl_cat.setObjectName(ObjectNames.FORM_LABEL)
        form_layout.addRow(lbl_cat, self.cmb_category)

        if self.mode == "edit":
            self.cmb_status = QComboBox()
            self.cmb_status.addItems(["OPEN", "COMPLETED", "OVERDUE", "RESOLVED"])
            lbl_status = QLabel("Status:")
            lbl_status.setObjectName(ObjectNames.FORM_LABEL)
            form_layout.addRow(lbl_status, self.cmb_status)

        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("Resolution notes (optional)")
        lbl_notes = QLabel("Notes:")
        lbl_notes.setObjectName(ObjectNames.FORM_LABEL)
        form_layout.addRow(lbl_notes, self.txt_notes)

        layout.addLayout(form_layout)

        if self.mode == "edit" and self.record:
            cat = self.record.get("category", "")
            idx = self.cmb_category.findText(cat)
            if idx >= 0:
                self.cmb_category.setCurrentIndex(idx)
            status = self.record.get("status", "")
            idx_s = self.cmb_status.findText(status)
            if idx_s >= 0:
                self.cmb_status.setCurrentIndex(idx_s)
            notes = self.record.get("resolution_notes") or ""
            self.txt_notes.setText(notes)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_save = QPushButton("✓  SAVE" if self.mode == "edit" else "✓  CREATE LOG")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_save.clicked.connect(self._handle_save)

        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _handle_save(self) -> None:
        category = self.cmb_category.currentText()
        notes = self.txt_notes.text().strip() or None

        try:
            if self.mode == "create":
                staff_id = self.cmb_staff.currentData()
                if staff_id is None:
                    QMessageBox.warning(self, "Error", "Please select a staff member.")
                    return
                new_id = self.att_repo.create_session(staff_id=staff_id, category=category)

                staff_label = self.cmb_staff.currentText()
                audit_ok = self._log_action(
                    action_type="CREATE",
                    entity_type="attendance_session",
                    entity_id=new_id,
                    reason=f"Manually created attendance log for '{staff_label}' (Category: {category}).",
                    old_values=None,
                    new_values={"staff_id": staff_id, "category": category, "notes": notes},
                )

                msg = "Manual attendance log created successfully."
                if not audit_ok:
                    msg += "\n\n(Note: this action could not be recorded in the audit trail.)"
                QMessageBox.information(self, "Success", msg)
            else:
                record_id = self.record["id"]
                status = self.cmb_status.currentText()
                existing_time_out = self.record.get("time_out")

                if status == "COMPLETED":
                    time_out = existing_time_out or get_utc_now_iso()
                elif status in ("OPEN", "OVERDUE"):
                    time_out = None
                else:
                    time_out = existing_time_out

                old_values = {
                    "category": self.record.get("category", ""),
                    "status": self.record.get("status", ""),
                    "time_out": existing_time_out,
                    "resolution_notes": self.record.get("resolution_notes"),
                }
                new_values = {
                    "category": category,
                    "status": status,
                    "time_out": time_out,
                    "resolution_notes": notes,
                }

                if self.is_visitor:
                    self.vis_repo.update_visit(
                        visit_id=record_id,
                        category=category,
                        status=status,
                        time_out=time_out,
                        resolution_notes=notes,
                    )
                    entity_type = "visitor_visit"
                else:
                    self.att_repo.update_session(
                        session_id=record_id,
                        category=category,
                        status=status,
                        time_out=time_out,
                        resolution_notes=notes,
                    )
                    entity_type = "attendance_session"

                name = self.record.get("full_name", "Unknown")
                audit_ok = self._log_action(
                    action_type="UPDATE",
                    entity_type=entity_type,
                    entity_id=record_id,
                    reason=f"Edited attendance record for '{name}' "
                           f"(Status: {old_values['status']} → {status}).",
                    old_values=old_values,
                    new_values=new_values,
                )

                msg = "Attendance record updated successfully."
                if not audit_ok:
                    msg += "\n\n(Note: this edit could not be recorded in the audit trail.)"
                QMessageBox.information(self, "Success", msg)

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))