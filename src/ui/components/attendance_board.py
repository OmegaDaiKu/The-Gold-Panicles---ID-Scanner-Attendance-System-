"""Live Attendance Board component displaying separate Time-In and Time-Out columns."""

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QEasingCurve, QSize, QVariantAnimation
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import Colors, ObjectNames
from src.ui.widgets.pill_widget import PillWidget


class _PillCellContainer(QWidget):
    """Transparent wrapper centering a fixed-size PillWidget within a table cell."""

    def __init__(self, pill: PillWidget, parent=None):
        super().__init__(parent)
        self.pill = pill
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(pill, 0, Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


class AttendanceBoardWidget(QWidget):
    """Custom QTableWidget rendering live staff attendance and visitor feed."""

    HEADERS = ["No.", "Time In", "Time Out", "ID Number", "Full Name", "Designation", "Purpose", "Status"]

    _HIGHLIGHT_COLOR = QColor(Colors.ACCENT_GOLD)
    _HIGHLIGHT_DURATION_MS = 1400
    _HIGHLIGHT_START_ALPHA = 0.55

    _PURPOSE_COLUMN = 6
    _STATUS_COLUMN = 7

    _CATEGORY_PILL_SIZE = QSize(84, 26)
    _STATUS_PILL_SIZE = QSize(112, 26)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._known_row_keys: set = set()
        self._first_populate: bool = True
        self._active_animations: List[QVariantAnimation] = []

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.container = QWidget()
        self.stack = QStackedLayout(self.container)
        self.stack.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setObjectName("attendanceBoardTable")

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)          # No.
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)          # Time In
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)          # Time Out
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)          # ID Number
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)        # Full Name
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)        # Designation
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)          # Purpose
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)          # Status

        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(6, 104)
        self.table.setColumnWidth(7, 136)

        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setShowGrid(False)

        self.lbl_empty = QLabel("No attendance activity recorded yet today.\nScanned badges will appear here.")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setObjectName(ObjectNames.EMPTY_STATE_LABEL)
        self.lbl_empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.stack.addWidget(self.table)
        self.stack.addWidget(self.lbl_empty)

        main_layout.addWidget(self.container)

    @staticmethod
    def _row_key(item: Dict) -> Tuple[str, str, str, str]:
        return (
            item.get("student_id_no", ""),
            item.get("time_in_display", "—"),
            item.get("time_out_display", "—"),
            item.get("status", ""),
        )

    @staticmethod
    def _category_pill_style(category_val: str) -> Tuple[QColor, QColor, Optional[QColor]]:
        normalized = (category_val or "").strip().upper()
        if normalized == "DUTY":
            return QColor(Colors.CHIP_DUTY_BG), QColor(Colors.ACCENT_GOLD_HOVER), None
        return QColor(Colors.CHIP_NEUTRAL_BG), QColor(Colors.TEXT_MUTED), None

    @staticmethod
    def _status_pill_style(status_val: str) -> Tuple[QColor, QColor, Optional[QColor]]:
        if status_val == "OPEN":
            return QColor(Colors.STATUS_OPEN_BG), QColor(Colors.STATUS_OPEN), QColor(Colors.STATUS_OPEN_BORDER)
        if status_val == "COMPLETED":
            return QColor(Colors.STATUS_COMPLETED_BG), QColor(Colors.STATUS_COMPLETED), QColor(Colors.STATUS_COMPLETED_BORDER)
        if status_val == "OVERDUE":
            return QColor(Colors.STATUS_OVERDUE_BG), QColor(Colors.STATUS_OVERDUE), QColor(Colors.STATUS_OVERDUE_BORDER)
        if status_val == "RESOLVED":
            return QColor(Colors.STATUS_RESOLVED_BG), QColor(Colors.STATUS_RESOLVED), QColor(Colors.STATUS_RESOLVED_BORDER)
        return QColor(Colors.CHIP_NEUTRAL_BG), QColor(Colors.TEXT_PRIMARY), QColor(Colors.BORDER_HOVER)

    def populate_feed(self, feed_data: List[Dict]) -> None:
        for anim in self._active_animations:
            anim.stop()
        self._active_animations.clear()

        self.table.setRowCount(0)

        if not feed_data:
            self.lbl_empty.setVisible(True)
            self._known_row_keys.clear()
            self._first_populate = True
            return

        self.lbl_empty.setVisible(False)

        previous_keys = self._known_row_keys
        current_keys = set()
        new_row_indices: List[int] = []

        for idx, item in enumerate(feed_data, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            category_text = item.get("category", "")
            status_text = item.get("status", "")

            items = [
                QTableWidgetItem(str(idx)),
                QTableWidgetItem(item.get("time_in_display", "—")),
                QTableWidgetItem(item.get("time_out_display", "—")),
                QTableWidgetItem(item.get("student_id_no", "")),
                QTableWidgetItem(item.get("full_name", "")),
                QTableWidgetItem(item.get("designation", "")),
                None,
                None,
            ]

            items[5].setForeground(QColor(Colors.TEXT_PRIMARY))

            if category_text.strip():
                bg, text_c, border = self._category_pill_style(category_text)
                pill = PillWidget(category_text, bg, text_c, border, fixed_size=self._CATEGORY_PILL_SIZE)
                self.table.setCellWidget(row_idx, self._PURPOSE_COLUMN, _PillCellContainer(pill))
            else:
                items[self._PURPOSE_COLUMN] = QTableWidgetItem("")

            if status_text.strip():
                bg, text_c, border = self._status_pill_style(status_text)
                pill = PillWidget(status_text, bg, text_c, border, fixed_size=self._STATUS_PILL_SIZE)
                self.table.setCellWidget(row_idx, self._STATUS_COLUMN, _PillCellContainer(pill))
            else:
                items[self._STATUS_COLUMN] = QTableWidgetItem("")

            for col_idx, table_item in enumerate(items):
                if table_item is None:
                    continue
                table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, col_idx, table_item)

            row_key = self._row_key(item)
            current_keys.add(row_key)
            if not self._first_populate and row_key not in previous_keys:
                new_row_indices.append(row_idx)

        self._known_row_keys = current_keys
        self._first_populate = False

        for row_idx in new_row_indices:
            self._animate_row_highlight(row_idx)

    def _animate_row_highlight(self, row_idx: int) -> None:
        row_items = [self.table.item(row_idx, col) for col in range(self.table.columnCount())]
        row_items = [it for it in row_items if it is not None]

        pill_widgets = []
        for col in range(self.table.columnCount()):
            widget = self.table.cellWidget(row_idx, col)
            if isinstance(widget, _PillCellContainer):
                pill_widgets.append(widget.pill)

        if not row_items and not pill_widgets:
            return

        anim = QVariantAnimation(self)
        anim.setStartValue(self._HIGHLIGHT_START_ALPHA)
        anim.setEndValue(0.0)
        anim.setDuration(self._HIGHLIGHT_DURATION_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        base_color = self._HIGHLIGHT_COLOR

        def _on_value_changed(value, items=row_items, pills=pill_widgets, color=base_color):
            fraction = max(0.0, min(1.0, float(value)))
            alpha = int(fraction * 255)
            if alpha <= 0:
                for it in items:
                    it.setData(Qt.ItemDataRole.BackgroundRole, None)
                for pill in pills:
                    pill.set_highlight_alpha(0)
                return
            faded = QColor(color.red(), color.green(), color.blue(), alpha)
            for it in items:
                it.setBackground(QBrush(faded))
            for pill in pills:
                pill.set_highlight_alpha(alpha)

        def _on_finished(anim_ref=anim):
            if anim_ref in self._active_animations:
                self._active_animations.remove(anim_ref)

        anim.valueChanged.connect(_on_value_changed)
        anim.finished.connect(_on_finished)

        self._active_animations.append(anim)
        anim.start()

    def update_feed(self, feed_data: List[Dict]) -> None:
        self.populate_feed(feed_data)


AttendanceBoard = AttendanceBoardWidget
LiveBoardWidget = AttendanceBoardWidget