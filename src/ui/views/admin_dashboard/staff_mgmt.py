"""
Staff Directory CRUD Management Tab with slot-capacity-aware designation selection.
"""

from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
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

from src.core.constants import DESIGNATION_DEPARTMENTS, get_slot_limit
from src.core.exceptions import AppError
from src.database.connection import DatabaseConnectionManager
from src.services.directory_service import DirectoryService
from src.ui.components.animations import attach_press_feedback
from src.ui.theme import Colors, ObjectNames, Radius, Spacing
from src.utils.icon_helper import IconHelper


class StaffManagementTab(QWidget):
    """Admin tab for registering, editing, listing, searching, and deleting publication staff."""

    HEADERS = ["#", "Student ID No", "Full Name", "Publication Designation", "Status", "Actions"]

    def __init__(self, db_manager: DatabaseConnectionManager, admin_id: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.admin_id = admin_id
        self.directory_service = DirectoryService(db_manager)
        self.editing_staff_id = None
        self._all_staff = []

        self._init_ui()
        self.refresh_table()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.LG)

        # Left Panel: Staff Directory Table
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(Spacing.MD)

        header_row = QHBoxLayout()
        header_row.setSpacing(Spacing.XS)

        icon_title = QLabel()
        icon_title.setPixmap(IconHelper.get_pixmap("users", color=Colors.ACCENT_GOLD, size=18))
        icon_title.setStyleSheet("background: transparent;")
        header_row.addWidget(icon_title)

        lbl_title = QLabel("STAFF DIRECTORY")
        lbl_title.setObjectName(ObjectNames.SECTION_TITLE)
        lbl_title.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 14px; font-weight: 800; letter-spacing: 0.8px;"
        )
        header_row.addWidget(lbl_title)
        header_row.addStretch()

        left_layout.addLayout(header_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(Spacing.SM)

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName(ObjectNames.SEARCH_INPUT)
        self.txt_search.setPlaceholderText("Search by Student ID or Name...")
        self.txt_search.addAction(
            IconHelper.get_icon("search", color=Colors.TEXT_MUTED, size=14),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.txt_search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self.txt_search, stretch=3)

        self.cmb_status_filter = QComboBox()
        self.cmb_status_filter.addItems(["All Staff", "Active Only", "Inactive Only"])
        self.cmb_status_filter.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self.cmb_status_filter, stretch=1)

        left_layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 210)

        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        left_layout.addWidget(self.table)

        self.lbl_count = QLabel("0 records")
        self.lbl_count.setObjectName(ObjectNames.TEXT_MUTED)
        self.lbl_count.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-family: monospace; font-size: 10px;")
        left_layout.addWidget(self.lbl_count)

        layout.addWidget(left_panel, stretch=7)

        # Right Panel: Registration & Edit Form
        right_panel = QFrame()
        right_panel.setObjectName(ObjectNames.SURFACE_CARD)
        right_panel.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px; }}"
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(Spacing.MD)
        right_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        self.lbl_form_title = QLabel("REGISTER NEW STAFF")
        self.lbl_form_title.setObjectName(ObjectNames.SECTION_TITLE)
        self.lbl_form_title.setStyleSheet(
            f"color: {Colors.ACCENT_GOLD}; font-size: 13px; font-weight: 800; letter-spacing: 0.8px; background: transparent;"
        )
        right_layout.addWidget(self.lbl_form_title)

        self.lbl_form_mode = QLabel()
        self.lbl_form_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_form_mode_badge(ObjectNames.FORM_MODE_CREATE, "Create Mode")
        right_layout.addWidget(self.lbl_form_mode)

        form_layout = QFormLayout()
        form_layout.setSpacing(Spacing.SM)

        self.txt_student_id = QLineEdit()
        self.txt_student_id.setObjectName(ObjectNames.GP_SUPER_INPUT)
        self.txt_student_id.setPlaceholderText("e.g. 261-00105")

        self.txt_full_name = QLineEdit()
        self.txt_full_name.setObjectName(ObjectNames.GP_SUPER_INPUT)
        self.txt_full_name.setPlaceholderText("Enter Full Name")

        self.cmb_designation = QComboBox()
        self._populate_designation_combo()
        self._select_first_available_designation()

        lbl_id = QLabel("Student ID No:")
        lbl_id.setObjectName(ObjectNames.FORM_LABEL)
        lbl_name = QLabel("Full Name:")
        lbl_name.setObjectName(ObjectNames.FORM_LABEL)
        lbl_desig = QLabel("Designation:")
        lbl_desig.setObjectName(ObjectNames.FORM_LABEL)

        form_layout.addRow(lbl_id, self.txt_student_id)
        form_layout.addRow(lbl_name, self.txt_full_name)
        form_layout.addRow(lbl_desig, self.cmb_designation)

        right_layout.addLayout(form_layout)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(Spacing.XS)

        self.btn_save = QPushButton(" REGISTER STAFF")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setObjectName(ObjectNames.BTN_PRIMARY)
        self.btn_save.setIcon(IconHelper.get_icon("user-plus", color=Colors.BACKGROUND, size=15))
        self.btn_save.clicked.connect(self._handle_save)
        attach_press_feedback(self.btn_save)

        self.btn_delete = QPushButton(" DELETE STAFF")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setObjectName(ObjectNames.BTN_DANGER_SOLID)
        self.btn_delete.setIcon(IconHelper.get_icon("trash-2", color="#FFFFFF", size=15))
        self.btn_delete.clicked.connect(self._handle_delete)
        self.btn_delete.setVisible(False)
        attach_press_feedback(self.btn_delete)

        self.btn_cancel = QPushButton("CANCEL / CLEAR")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        self.btn_cancel.setIcon(IconHelper.get_icon("x-circle", color=Colors.TEXT_MUTED, size=15))
        self.btn_cancel.clicked.connect(self._reset_form)
        attach_press_feedback(self.btn_cancel)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_cancel)
        right_layout.addLayout(btn_layout)

        right_layout.addStretch()
        layout.addWidget(right_panel, stretch=3)

    def _set_form_mode_badge(self, object_name: str, text: str) -> None:
        self.lbl_form_mode.setObjectName(object_name)
        self.lbl_form_mode.setText(text)
        self.lbl_form_mode.style().unpolish(self.lbl_form_mode)
        self.lbl_form_mode.style().polish(self.lbl_form_mode)

    def _populate_designation_combo(self, keep_designation: Optional[str] = None) -> None:
        counts = self.directory_service.staff_repo.get_active_designation_counts()
        model = QStandardItemModel(self.cmb_designation)

        for department, designations in DESIGNATION_DEPARTMENTS.items():
            header_item = QStandardItem(f"— {department} —")
            header_item.setFlags(Qt.ItemFlag.NoItemFlags)
            header_item.setForeground(QColor(Colors.TEXT_MUTED))
            model.appendRow(header_item)

            for designation in designations:
                limit = get_slot_limit(designation)
                current_count = counts.get(designation, 0)
                is_full = limit is not None and current_count >= limit
                is_kept = keep_designation is not None and designation == keep_designation

                if limit is None:
                    label = designation
                elif is_full:
                    label = f"{designation}  ({current_count}/{limit}) — FULL"
                else:
                    label = f"{designation}  ({current_count}/{limit})"

                item = QStandardItem(label)
                item.setData(designation, Qt.ItemDataRole.UserRole)

                if is_full and not is_kept:
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    item.setForeground(QColor(Colors.TEXT_MUTED))

                model.appendRow(item)

        self.cmb_designation.setModel(model)

    def _select_designation(self, designation: str) -> None:
        model = self.cmb_designation.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == designation:
                self.cmb_designation.setCurrentIndex(row)
                return

    def _select_first_available_designation(self) -> None:
        model = self.cmb_designation.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is not None and item.isEnabled():
                self.cmb_designation.setCurrentIndex(row)
                return

    def _refresh_designation_availability(self) -> None:
        current_value = self.cmb_designation.currentData(Qt.ItemDataRole.UserRole)
        keep = current_value if self.editing_staff_id is not None else None
        self._populate_designation_combo(keep_designation=keep)
        if current_value:
            self._select_designation(current_value)
        else:
            self._select_first_available_designation()

    def refresh_table(self) -> None:
        self._all_staff = self.directory_service.list_staff(active_only=False)
        self._apply_filter()
        self._refresh_designation_availability()

    def _apply_filter(self) -> None:
        search_text = self.txt_search.text().strip().lower()
        status_filter = self.cmb_status_filter.currentIndex()

        filtered = []
        for staff in self._all_staff:
            if status_filter == 1 and staff["is_active"] != 1:
                continue
            if status_filter == 2 and staff["is_active"] != 0:
                continue
            if search_text:
                if (
                    search_text not in staff["student_id_no"].lower()
                    and search_text not in staff["full_name"].lower()
                ):
                    continue
            filtered.append(staff)

        self._render_rows(filtered)
        self.lbl_count.setText(f"Showing: {len(filtered)} of {len(self._all_staff)} staff records")

    def _render_rows(self, staff_list: list) -> None:
        self.table.setRowCount(0)

        for idx, staff in enumerate(staff_list, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            items = [
                QTableWidgetItem(str(idx)),
                QTableWidgetItem(staff["student_id_no"]),
                QTableWidgetItem(staff["full_name"]),
                QTableWidgetItem(staff["designation"]),
                QTableWidgetItem("ACTIVE" if staff["is_active"] == 1 else "INACTIVE"),
            ]

            items[3].setForeground(QColor(Colors.ACCENT_GOLD))
            status_item = items[4]
            if staff["is_active"] == 1:
                status_item.setForeground(QColor(Colors.STATUS_OPEN))
            else:
                status_item.setForeground(QColor(Colors.STATUS_OVERDUE))

            for col_idx, table_item in enumerate(items):
                table_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter if col_idx in (0, 1, 4) else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row_idx, col_idx, table_item)

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            btn_edit = QPushButton("EDIT")
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.setObjectName(ObjectNames.BTN_ROW_EDIT)
            btn_edit.setIcon(IconHelper.get_icon("edit-2", color=Colors.TEXT_PRIMARY, size=12))
            btn_edit.setIconSize(QSize(12, 12))
            btn_edit.clicked.connect(lambda _, s=staff: self._populate_edit(s))
            attach_press_feedback(btn_edit)

            btn_toggle = QPushButton("DEACTIVATE" if staff["is_active"] == 1 else "REACTIVATE")
            btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            if staff["is_active"] == 1:
                btn_toggle.setObjectName(ObjectNames.BTN_ROW_WARNING)
                btn_toggle.setIcon(IconHelper.get_icon("user-x", color=Colors.TEXT_PRIMARY, size=12))
            else:
                btn_toggle.setObjectName(ObjectNames.BTN_ROW_SUCCESS)
                btn_toggle.setIcon(IconHelper.get_icon("user-check", color=Colors.TEXT_PRIMARY, size=12))
            btn_toggle.setIconSize(QSize(12, 12))
            btn_toggle.clicked.connect(lambda _, s=staff: self._toggle_status(s))
            attach_press_feedback(btn_toggle)

            actions_layout.addWidget(btn_edit)
            actions_layout.addWidget(btn_toggle)
            self.table.setCellWidget(row_idx, 5, actions_widget)

    def _on_row_double_clicked(self, row: int, _col: int) -> None:
        student_id_item = self.table.item(row, 1)
        if student_id_item:
            student_id = student_id_item.text()
            for s in self._all_staff:
                if s["student_id_no"] == student_id:
                    self._populate_edit(s)
                    break

    def _populate_edit(self, staff: dict) -> None:
        self.editing_staff_id = staff["id"]
        self.txt_student_id.setText(staff["student_id_no"])
        self.txt_student_id.setReadOnly(True)
        self.txt_full_name.setText(staff["full_name"])

        self._populate_designation_combo(keep_designation=staff["designation"])
        self._select_designation(staff["designation"])

        self.lbl_form_title.setText("EDIT STAFF RECORD")
        self.btn_save.setText(" UPDATE STAFF")
        self.btn_save.setIcon(IconHelper.get_icon("check", color=Colors.BACKGROUND, size=15))
        self.btn_delete.setVisible(True)
        self._set_form_mode_badge(ObjectNames.FORM_MODE_EDIT, "Edit Mode")

    def _handle_save(self) -> None:
        student_id = self.txt_student_id.text().strip()
        full_name = self.txt_full_name.text().strip()
        designation = self.cmb_designation.currentData(Qt.ItemDataRole.UserRole)

        if not designation:
            QMessageBox.warning(self, "Missing Designation", "Please select a valid designation.")
            return

        exclude_pk = self.editing_staff_id
        if not self.directory_service.staff_repo.has_available_slot(designation, exclude_pk=exclude_pk):
            limit = get_slot_limit(designation)
            QMessageBox.warning(
                self,
                "Designation Full",
                f"'{designation}' already has all {limit} slot(s) filled by active staff.\n\n"
                f"Deactivate or reassign an existing holder before assigning this designation "
                f"to someone else.",
            )
            self._refresh_designation_availability()
            return

        try:
            if self.editing_staff_id is None:
                self.directory_service.register_staff(
                    student_id_no=student_id,
                    full_name=full_name,
                    designation=designation,
                    admin_id=self.admin_id,
                )
                QMessageBox.information(self, "Success", f"Staff member '{full_name}' registered successfully.")
            else:
                self.directory_service.update_staff(
                    staff_id=self.editing_staff_id,
                    full_name=full_name,
                    designation=designation,
                    admin_id=self.admin_id,
                )
                QMessageBox.information(self, "Success", "Staff record updated successfully.")

            self._reset_form()
            self.refresh_table()

        except AppError as e:
            QMessageBox.critical(self, "Validation Error", str(e))
        except ValueError as e:
            QMessageBox.critical(self, "Validation Error", str(e))

    def _handle_delete(self) -> None:
        if self.editing_staff_id is None:
            return

        staff = self.directory_service.staff_repo.get_by_id(self.editing_staff_id)
        if not staff:
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the staff record for:\n\n"
            f"  {staff['full_name']}  ({staff['student_id_no']})\n\n"
            f"If this staffer has attendance history, they will be deactivated instead "
            f"of permanently deleted, to preserve historical records.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                result = self.directory_service.delete_staff(self.editing_staff_id, admin_id=self.admin_id)
                if result.get("status") == "deactivated":
                    QMessageBox.information(
                        self,
                        "Deactivated",
                        "This staff member has existing attendance history and cannot be "
                        "permanently deleted. The record has been deactivated instead.",
                    )
                else:
                    QMessageBox.information(self, "Deleted", "Staff record has been permanently deleted.")
                self._reset_form()
                self.refresh_table()
            except AppError as e:
                QMessageBox.critical(self, "Error", str(e))

    def _toggle_status(self, staff: dict) -> None:
        target_status = 0 if staff["is_active"] == 1 else 1
        action_word = "deactivate" if target_status == 0 else "reactivate"

        reply = QMessageBox.question(
            self,
            "Confirm Action",
            f"Are you sure you want to {action_word} '{staff['full_name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.directory_service.set_staff_active_status(
                    staff["id"],
                    is_active=target_status,
                    admin_id=self.admin_id,
                )
                self.refresh_table()
            except AppError as e:
                QMessageBox.critical(self, "Error", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to {action_word} staff record:\n{e}")

    def _reset_form(self) -> None:
        self.editing_staff_id = None
        self.txt_student_id.clear()
        self.txt_student_id.setReadOnly(False)
        self.txt_full_name.clear()
        self._populate_designation_combo()
        self._select_first_available_designation()
        self.lbl_form_title.setText("REGISTER NEW STAFF")
        self.btn_save.setText(" REGISTER STAFF")
        self.btn_save.setIcon(IconHelper.get_icon("user-plus", color=Colors.BACKGROUND, size=15))
        self.btn_delete.setVisible(False)
        self._set_form_mode_badge(ObjectNames.FORM_MODE_CREATE, "Create Mode")