""""Live Attendance Board component displaying staff duty and guest visitor activity stream."""

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QEasingCurve, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QFont
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

from src.ui.theme import Colors, ObjectNames, Radius, Spacing, Typography
from src.ui.widgets.pill_widget import PillWidget


class _PillCellContainer(QWidget):
    """Transparent wrapper centering a PillWidget within a table cell."""

    def __init__(self, pill: PillWidget, parent=None):
        super().__init__(parent)
        self.pill = pill
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(pill, 0, Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent; border: none;")


class AttendanceBoardWidget(QWidget):
    """Custom QTableWidget rendering live staff attendance and visitor feed."""

    HEADERS = ["NO.", "TIME IN", "TIME OUT", "ID NUMBER", "FULL NAME", "DESIGNATION", "PURPOSE", "STATUS"]

    _HIGHLIGHT_COLOR = Colors.parse_qcolor(Colors.ACCENT_GOLD)
    _HIGHLIGHT_DURATION_MS = 1000
    _HIGHLIGHT_START_ALPHA = 0.20  # Subtle Apple HIG soft pulse glow

    _PURPOSE_COLUMN = 6
    _STATUS_COLUMN = 7

    _CATEGORY_PILL_SIZE = QSize(76, 22)
    _STATUS_PILL_SIZE = QSize(82, 22)

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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)

        # 8-Point Spatial Grid Column Widths
        self.table.setColumnWidth(0, 48)
        self.table.setColumnWidth(1, 96)
        self.table.setColumnWidth(2, 96)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(6, 96)
        self.table.setColumnWidth(7, 96)

        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)  # 8-pt grid standardized
        self.table.setAlternatingRowColors(False)
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
        if normalized in ("VISIT", "VISITOR"):
            return (
                Colors.parse_qcolor(Colors.PURPOSE_VISIT_BG),
                Colors.parse_qcolor(Colors.PURPOSE_VISIT),
                Colors.parse_qcolor("rgba(56, 189, 248, 0.28)"),
            )
        return (
            Colors.parse_qcolor(Colors.PURPOSE_DUTY_BG),
            Colors.parse_qcolor(Colors.PURPOSE_DUTY),
            Colors.parse_qcolor("rgba(226, 184, 66, 0.28)"),
        )

    @staticmethod
    def _status_pill_style(status_val: str) -> Tuple[QColor, QColor, Optional[QColor], str]:
        normalized = (status_val or "").strip().upper()
        if normalized in ("IN", "OPEN", "DUTY"):
            return (
                Colors.parse_qcolor(Colors.STATUS_IN_BG),
                Colors.parse_qcolor(Colors.STATUS_IN),
                Colors.parse_qcolor(Colors.STATUS_IN_BORDER),
                "IN",
            )
        if normalized in ("OUT", "COMPLETED"):
            return (
                Colors.parse_qcolor(Colors.STATUS_OUT_BG),
                Colors.parse_qcolor(Colors.STATUS_OUT),
                Colors.parse_qcolor(Colors.STATUS_OUT_BORDER),
                "OUT",
            )
        if normalized == "OVERDUE":
            return (
                Colors.parse_qcolor(Colors.STATUS_OVERDUE_BG),
                Colors.parse_qcolor(Colors.STATUS_OVERDUE),
                Colors.parse_qcolor(Colors.STATUS_OVERDUE_BORDER),
                "OVERDUE",
            )
        return (
            Colors.parse_qcolor(Colors.SURFACE_ALT),
            Colors.parse_qcolor(Colors.TEXT_PRIMARY),
            Colors.parse_qcolor(Colors.BORDER),
            normalized,
        )

    def populate_feed(self, feed_data: List[Dict]) -> None:
        for anim in self._active_animations:
            anim.stop()
        self._active_animations.clear()

        self.table.setRowCount(0)

        if not feed_data:
            self.lbl_empty.setVisible(True)
            self._known_row_keys.clear()
            self._first_populate = True
            self.table.viewport().update()
            return

        self.lbl_empty.setVisible(False)

        previous_keys = self._known_row_keys
        current_keys = set()
        new_row_indices: List[int] = []

        mono_font = QFont(Typography.MONO_FAMILY, 9.5)

        for idx, item in enumerate(feed_data, start=1):
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            category_text = item.get("category", "DUTY")
            status_text = item.get("status", "IN")

            items = [
                QTableWidgetItem(str(idx)),
                QTableWidgetItem(item.get("time_in_display", "—")),
                QTableWidgetItem(item.get("time_out_display", "—")),
                QTableWidgetItem(item.get("student_id_no", "")),
                QTableWidgetItem(item.get("full_name", "")),
                QTableWidgetItem(item.get("designation", "")),
                QTableWidgetItem(""),  # Purpose backing item
                QTableWidgetItem(""),  # Status backing item
            ]

            for col_i in (0, 1, 2, 3):
                items[col_i].setFont(mono_font)

            items[0].setForeground(Colors.parse_qcolor(Colors.TEXT_MUTED))
            items[1].setForeground(Colors.parse_qcolor(Colors.TEXT_PRIMARY))
            items[2].setForeground(Colors.parse_qcolor(Colors.TEXT_PRIMARY))
            items[3].setForeground(Colors.parse_qcolor(Colors.TEXT_SECONDARY))
            items[4].setForeground(Colors.parse_qcolor(Colors.TEXT_PRIMARY))
            items[5].setForeground(Colors.parse_qcolor(Colors.TEXT_MUTED))

            for col_idx, table_item in enumerate(items):
                table_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter if col_idx in (0, 1, 2, 3, 6, 7) else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.table.setItem(row_idx, col_idx, table_item)

            if category_text.strip():
                bg, text_c, border = self._category_pill_style(category_text)
                pill = PillWidget(category_text.upper(), bg, text_c, border, fixed_size=self._CATEGORY_PILL_SIZE)
                self.table.setCellWidget(row_idx, self._PURPOSE_COLUMN, _PillCellContainer(pill))

            if status_text.strip():
                bg, text_c, border, pill_label = self._status_pill_style(status_text)
                pill = PillWidget(pill_label, bg, text_c, border, fixed_size=self._STATUS_PILL_SIZE)
                self.table.setCellWidget(row_idx, self._STATUS_COLUMN, _PillCellContainer(pill))

            row_key = self._row_key(item)
            current_keys.add(row_key)
            if not self._first_populate and row_key not in previous_keys:
                new_row_indices.append(row_idx)

        self._known_row_keys = current_keys
        self._first_populate = False

        for row_idx in new_row_indices:
            self._animate_row_highlight(row_idx)

        # Force immediate view update to guarantee rendering even during high-frequency focus guarding
        self.table.viewport().update()

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
                transparent_brush = QBrush(Qt.GlobalColor.transparent)
                for it in items:
                    it.setBackground(transparent_brush)
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