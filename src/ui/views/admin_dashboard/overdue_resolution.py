"""Overdue Resolution View for managing and forcing check-outs on active staff/visitors crossing midnight/overdue limits."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from src.core.exceptions import AppError
from src.ui.theme import ObjectNames


class OverdueResolutionView(QWidget):
    """Admin view for reviewing and resolving lingering/overdue attendance entries."""

    resolution_completed = Signal()

    def __init__(self, db_manager=None, overdue_service=None, admin_id=None, parent=None, **kwargs):
        super().__init__(parent)
        self.db_manager = db_manager

        if admin_id is None:
            raise ValueError(
                "OverdueResolutionView requires a valid 'admin_id'. Received: {!r}".format(admin_id)
            )
        self.admin_id = admin_id

        if overdue_service is not None:
            self.overdue_service = overdue_service
        elif db_manager is not None:
            from src.services.overdue_service import OverdueService
            self.overdue_service = OverdueService(db_manager)
        else:
            self.overdue_service = None
        self._init_ui()

    def refresh_table(self):
        self.refresh_overdue_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header_card = QFrame()
        header_card.setObjectName(ObjectNames.SURFACE_CARD)
        header_layout = QVBoxLayout(header_card)

        title = QLabel("Overdue Attendance & Force Check-Out")
        title.setObjectName(ObjectNames.SECTION_TITLE_DANGER)

        desc = QLabel(
            "Review active sessions that have exceeded maximum allowed duration or crossed midnight PHT. "
            "Use force check-out to resolve lingering records."
        )
        desc.setObjectName(ObjectNames.TEXT_SECONDARY)
        desc.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(desc)
        layout.addWidget(header_card)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Log ID", "Name / Visitor", "Type", "Time In (PHT)", "Duration", "Action"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        action_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_refresh.setObjectName(ObjectNames.BTN_CHROME)
        self.btn_refresh.clicked.connect(self.refresh_overdue_list)
        action_layout.addWidget(self.btn_refresh)
        action_layout.addStretch()

        layout.addLayout(action_layout)

    def refresh_overdue_list(self):
        if not self.overdue_service:
            return

        records = self.overdue_service.get_overdue_records()
        self.table.setRowCount(0)

        for row_idx, record in enumerate(records):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(record.get("id", ""))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(record.get("name", "Unknown"))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(record.get("person_type", "Staff"))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(record.get("time_in_pht", ""))))

            duration = str(record.get("duration", "N/A"))
            if duration != "":
                duration_item = QTableWidgetItem(duration)
            else:
                duration_item = QTableWidgetItem("Overdue")
            self.table.setItem(row_idx, 4, duration_item)

            btn_force = QPushButton("Force Check-Out")
            btn_force.setObjectName(ObjectNames.BTN_ROW_DELETE)
            log_id = record.get("id")
            is_visitor = bool(record.get("is_visitor", False))
            btn_force.clicked.connect(
                lambda _, lid=log_id, is_vis=is_visitor: self._handle_force_checkout(lid, is_vis)
            )
            self.table.setCellWidget(row_idx, 5, btn_force)

    def _handle_force_checkout(self, log_id: int, is_visitor: bool):
        reply = QMessageBox.question(
            self,
            "Confirm Force Check-Out",
            f"Are you sure you want to force check-out Log ID #{log_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes or not self.overdue_service:
            return

        try:
            self.overdue_service.force_checkout_log(
                log_id,
                is_visitor=is_visitor,
                admin_id=self.admin_id,
            )
            QMessageBox.information(self, "Success", f"Log #{log_id} successfully checked out.")
            self.refresh_overdue_list()
            self.resolution_completed.emit()
        except AppError as e:
            QMessageBox.warning(self, "Error", f"Failed to force check-out Log #{log_id}:\n{e}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Unexpected error checking out Log #{log_id}:\n{e}")


OverdueResolutionTab = OverdueResolutionView