""""Custom calendar grid widget for the Gold Panicles station view."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.ui.theme import Colors, Radius, Spacing, Typography

_WEEKDAY_LABELS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
_ROWS = 6
_COLS = 7


class _CalendarDayCell(QWidget):
    """Custom-painted calendar day cell with vector activity indicators and Apple HIG states."""

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._date: QDate = QDate.currentDate()
        self._in_month: bool = True
        self._is_today: bool = False
        self._is_selected: bool = False
        self._has_record: bool = False
        self._is_future: bool = False
        self._is_pressed: bool = False

        # Compact 26px height prevents sidebar card bottom clipping
        self.setFixedHeight(26)

        font = QFont(Typography.MONO_FAMILY, 9.5)
        font.setWeight(QFont.Weight.Bold)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self.setFont(font)

    def set_cell_state(
        self,
        date: QDate,
        in_month: bool,
        is_today: bool,
        is_selected: bool,
        has_record: bool,
        is_future: bool,
        is_enabled: bool,
    ) -> None:
        self._date = date
        self._in_month = in_month
        self._is_today = is_today
        self._is_selected = is_selected
        self._has_record = has_record
        self._is_future = is_future

        self.setEnabled(is_enabled)
        if is_enabled:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        self.update()

    def date(self) -> QDate:
        return self._date

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self._is_pressed = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._is_pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_pressed:
            self._is_pressed = False
            self.update()
            if self.rect().contains(event.position().toPoint()) and self.isEnabled():
                self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter()
        if not painter.begin(self):
            return

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
            radius = float(getattr(Radius, "CHIP", 6))

            # State Determination & Color Palette
            if not self._in_month or self._is_future or (not self._has_record and not self._is_today):
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(Qt.PenStyle.NoPen)
                text_color = QColor(Colors.TEXT_MUTED)
                text_color.setAlpha(80 if self._in_month else 40)
            elif self._is_selected:
                painter.setBrush(QColor(Colors.ACCENT_GOLD))
                painter.setPen(Qt.PenStyle.NoPen)
                text_color = QColor(Colors.BACKGROUND)
            elif self._is_today:
                bg_tint = QColor(Colors.ACCENT_GOLD)
                bg_tint.setAlpha(26 if not self._is_pressed else 50)
                painter.setBrush(bg_tint)
                painter.setPen(QPen(QColor(Colors.ACCENT_GOLD), 1.0))
                text_color = QColor(Colors.ACCENT_GOLD)
            else:
                if self._is_pressed and self.isEnabled():
                    painter.setBrush(QColor(Colors.SURFACE_ELEVATED))
                    painter.setPen(QPen(QColor(Colors.ACCENT_GOLD_PRESSED), 1.0))
                    text_color = QColor(Colors.ACCENT_GOLD_PRESSED)
                elif self.underMouse() and self.isEnabled():
                    painter.setBrush(QColor("rgba(226, 184, 66, 0.12)"))
                    painter.setPen(QPen(QColor("rgba(226, 184, 66, 0.30)"), 1.0))
                    text_color = QColor(Colors.ACCENT_GOLD)
                else:
                    painter.setBrush(QColor(Colors.SURFACE_ALT))
                    painter.setPen(QPen(QColor(Colors.BORDER), 1.0))
                    text_color = QColor(Colors.TEXT_PRIMARY)

            # Draw Surface
            if painter.brush() != Qt.BrushStyle.NoBrush or painter.pen().style() != Qt.PenStyle.NoPen:
                painter.drawRoundedRect(rect, radius, radius)

            # Draw Date Label & Gold Activity Indicator Dot
            font = self.font()
            font.setWeight(QFont.Weight.Black if (self._is_selected or self._is_today) else QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(text_color)

            if self._has_record and self._in_month and not self._is_future and not self._is_selected:
                text_rect = QRectF(rect.x(), rect.y() - 1, rect.width(), rect.height() - 5)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(self._date.day()))

                # Muted Activity Indicator Dot
                dot_radius = 1.75
                dot_center_x = rect.center().x()
                dot_center_y = rect.bottom() - 4.5
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(Colors.ACCENT_GOLD))
                painter.drawEllipse(QPointF(dot_center_x, dot_center_y), dot_radius, dot_radius)
            else:
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._date.day()))
        finally:
            painter.end()


class GoldCalendar(QWidget):
    """Custom month calendar grid with Obsidian Gold theme styling and activity indicators."""

    dateSelected = Signal(QDate)
    pageChanged = Signal(int, int)
    canNavigateNextChanged = Signal(bool)
    canNavigatePrevChanged = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        today = QDate.currentDate()
        self._shown_year = today.year()
        self._shown_month = today.month()
        self._selected_date = today
        self._max_date: Optional[QDate] = None
        self._highlighted_dates: Optional[set] = None
        self._day_cells: list[_CalendarDayCell] = []

        self._build_ui()
        self._render_month()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Weekday Headers Row
        weekday_row = QHBoxLayout()
        weekday_row.setContentsMargins(0, 0, 0, 2)
        weekday_row.setSpacing(2)
        for label_text in _WEEKDAY_LABELS:
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {Colors.TEXT_MUTED}; font-size: 9.5px; font-weight: 800; "
                f"font-family: {Typography.MONO_FAMILY}; letter-spacing: 0.5px; background: transparent; border: none;"
            )
            weekday_row.addWidget(lbl)
        layout.addLayout(weekday_row)

        # Days Grid Matrix
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        for row in range(_ROWS):
            for col in range(_COLS):
                cell = _CalendarDayCell()
                cell.clicked.connect(lambda c=cell: self._on_cell_clicked(c))
                grid.addWidget(cell, row, col)
                self._day_cells.append(cell)
        layout.addLayout(grid, stretch=1)

    def set_maximum_date(self, date: QDate) -> None:
        self._max_date = date
        self._render_month()

    def set_selected_date(self, date: QDate) -> None:
        self._selected_date = date
        self._shown_year = date.year()
        self._shown_month = date.month()
        self._render_month()
        self.pageChanged.emit(self._shown_year, self._shown_month)

    def selected_date(self) -> QDate:
        return self._selected_date

    def year_shown(self) -> int:
        return self._shown_year

    def month_shown(self) -> int:
        return self._shown_month

    def set_highlighted_dates(self, dates: Optional[set]) -> None:
        self._highlighted_dates = dates
        self._render_month()

    def show_today(self) -> None:
        today = QDate.currentDate()
        self._shown_year = today.year()
        self._shown_month = today.month()
        self._render_month()
        self.pageChanged.emit(self._shown_year, self._shown_month)

    def _has_prior_records(self, year: int, month: int) -> bool:
        if not self._highlighted_dates:
            return False
        prefix = f"{year:04d}-{month:02d}"
        return any(d[:7] < prefix for d in self._highlighted_dates)

    def can_navigate_previous(self) -> bool:
        if self._highlighted_dates is None:
            return True
        return self._has_prior_records(self._shown_year, self._shown_month)

    def can_navigate_next(self) -> bool:
        if self._max_date is None:
            return True
        return (self._shown_year, self._shown_month) < (self._max_date.year(), self._max_date.month())

    def go_previous_month(self) -> None:
        if not self.can_navigate_previous():
            return
        self._shown_month -= 1
        if self._shown_month < 1:
            self._shown_month = 12
            self._shown_year -= 1
        self._render_month()
        self.pageChanged.emit(self._shown_year, self._shown_month)

    def go_next_month(self) -> None:
        if not self.can_navigate_next():
            return
        self._shown_month += 1
        if self._shown_month > 12:
            self._shown_month = 1
            self._shown_year += 1
        self._render_month()
        self.pageChanged.emit(self._shown_year, self._shown_month)

    def _on_cell_clicked(self, cell: _CalendarDayCell) -> None:
        date = cell.date()
        if date.isValid():
            self.dateSelected.emit(date)

    def _render_month(self) -> None:
        first_of_month = QDate(self._shown_year, self._shown_month, 1)
        dow = first_of_month.dayOfWeek()
        start_offset = 0 if dow == 7 else dow
        grid_start = first_of_month.addDays(-start_offset)

        today = QDate.currentDate()

        for i, cell in enumerate(self._day_cells):
            d = grid_start.addDays(i)

            in_month = d.month() == self._shown_month
            is_future = self._max_date is not None and d > self._max_date
            is_selected = d == self._selected_date
            is_today = d == today

            has_record = False
            if self._highlighted_dates is not None:
                has_record = d.toString("yyyy-MM-dd") in self._highlighted_dates
            elif in_month and not is_future:
                has_record = True

            btn_enabled = in_month and not is_future and (has_record or is_today)
            cell.set_cell_state(
                date=d,
                in_month=in_month,
                is_today=is_today,
                is_selected=is_selected,
                has_record=has_record,
                is_future=is_future,
                is_enabled=btn_enabled,
            )

        self.canNavigateNextChanged.emit(self.can_navigate_next())
        self.canNavigatePrevChanged.emit(self.can_navigate_previous())