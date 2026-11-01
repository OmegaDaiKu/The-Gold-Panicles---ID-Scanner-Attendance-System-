"""
Overdue Resolution View for managing and forcing check-outs on active staff/visitors crossing midnight/overdue limits.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.exceptions import AppError
from src.ui.components.animations import attach_press_feedback
from src.ui.theme import Colors, ObjectNames, Radius, Spacing
from src.utils.icon_helper import IconHelper


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
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)

        header_card = QFrame()
        header_card.setObjectName(ObjectNames.SURFACE_CARD)
        header_card.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-left: 4px solid {Colors.DANGER_SOLID}; border-radius: {Radius.CARD}px; }}"
        )
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        header_layout.setSpacing(Spacing.XS)

        title_row = QHBoxLayout()
        title_row.setSpacing(Spacing.XS)

        icon_alert = QLabel()
        icon_alert.setPixmap(IconHelper.get_pixmap("alert-triangle", color=Colors.DANGER_SOLID, size=18))
        icon_alert.setStyleSheet("background: transparent;")
        title_row.addWidget(icon_alert)

        title = QLabel("OVERDUE ATTENDANCE & FORCE CHECK-OUT")
        title.setObjectName(ObjectNames.SECTION_TITLE_DANGER)
        title.setStyleSheet(
            f"color: {Colors.DANGER_SOLID}; font-size: 14px; font-weight: 800; letter-spacing: 0.8px; background: transparent;"
        )
        title_row.addWidget(title)
        title_row.addStretch()

        header_layout.addLayout(title_row)

        desc = QLabel(
            "Review active sessions that have exceeded maximum allowed duration or crossed midnight PHT. "
            "Use force check-out to resolve lingering records and preserve audit trail compliance."
        )
        desc.setObjectName(ObjectNames.TEXT_SECONDARY)
        desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        desc.setWordWrap(True)

        header_layout.addWidget(desc)
        layout.addWidget(header_card)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Log ID", "Name / Visitor", "Type", "Time In (PHT)", "Duration", "Action"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 170)

        layout.addWidget(self.table)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(Spacing.SM)

        self.btn_refresh = QPushButton(" Refresh List")
        self.btn_refresh.setObjectName(ObjectNames.BTN_CHROME)
        self.btn_refresh.setIcon(IconHelper.get_icon("rotate-cw", color=Colors.TEXT_PRIMARY, size=14))
        self.btn_refresh.setIconSize(QSize(14, 14))
        self.btn_refresh.clicked.connect(self.refresh_overdue_list)
        attach_press_feedback(self.btn_refresh)

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

            id_item = QTableWidgetItem(str(record.get("id", "")))
            name_item = QTableWidgetItem(str(record.get("name", "Unknown")))
            type_item = QTableWidgetItem(str(record.get("person_type", "Staff")))
            time_item = QTableWidgetItem(str(record.get("time_in_pht", "")))

            duration = str(record.get("duration", "N/A"))
            duration_item = QTableWidgetItem(duration if duration != "" else "Overdue")
            duration_item.setForeground(QColor(Colors.DANGER_SOLID))

            items = [id_item, name_item, type_item, time_item, duration_item]

            for col_idx, table_item in enumerate(items):
                table_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter if col_idx in (0, 2, 3, 4) else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row_idx, col_idx, table_item)

            btn_force = QPushButton("Force Check-Out")
            btn_force.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_force.setObjectName(ObjectNames.BTN_ROW_DELETE)
            btn_force.setIcon(IconHelper.get_icon("log-out", color="#FFFFFF", size=12))
            btn_force.setIconSize(QSize(12, 12))

            log_id = record.get("id")
            is_visitor = bool(record.get("is_visitor", False))
            btn_force.clicked.connect(
                lambda _, lid=log_id, is_vis=is_visitor: self._handle_force_checkout(lid, is_vis)
            )
            attach_press_feedback(btn_force)

            self.table.setCellWidget(row_idx, 5, btn_force)

    def _handle_force_checkout(self, log_id: int, is_visitor: bool):
        reply = QMessageBox.question(
            self,
            "Confirm Force Check-Out",
            f"Are you sure you want to force check-out Log ID #{log_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes or not self.overdue_service:
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