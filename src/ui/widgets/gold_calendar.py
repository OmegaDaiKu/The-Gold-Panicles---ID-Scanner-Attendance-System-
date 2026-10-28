"""Custom hand-rolled calendar grid widget for the Gold Panicles station view.

Built from scratch (QWidget + QGridLayout of QPushButton day cells) instead
of QCalendarWidget, because QCalendarWidget's internal views (native nav bar,
QAbstractItemView day grid, QToolButton month/year selectors) are notoriously
difficult to restyle consistently across Qt versions/platforms and fought the
bespoke Obsidian/Gold theme in previous iterations. This widget is fully
owned, fully themeable, and reuses the same press-feedback micro-interaction
as the rest of the app.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui.components.animations import attach_press_feedback

_WEEKDAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"]
_ROWS = 6
_COLS = 7

_COLOR_SELECTED_BG = "#DAA520"
_COLOR_SELECTED_BG_HOVER = "#E8B82E"
_COLOR_SELECTED_TEXT = "#0B0B0C"
_COLOR_TODAY_BORDER = "#DAA520"
_COLOR_TODAY_TEXT = "#DAA520"
_COLOR_WEEKEND_TEXT = "#E0626E"
_COLOR_NORMAL_TEXT = "#F4EFEA"
_COLOR_NO_RECORD_TEXT = "#55555C"
_COLOR_OUTSIDE_MONTH_TEXT = "#303034"
_COLOR_CELL_HOVER_BG = "#1C1C20"


class GoldCalendar(QWidget):
    """A permanently-embedded, fully custom-themed month calendar grid."""

    dateSelected = Signal(QDate)
    pageChanged = Signal(int, int)  # year, month
    canNavigateNextChanged = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        today = QDate.currentDate()
        self._shown_year = today.year()
        self._shown_month = today.month()
        self._selected_date = today
        self._max_date: Optional[QDate] = None
        self._highlighted_dates: Optional[set] = None
        self._day_buttons: list[QPushButton] = []

        self._build_ui()
        self._render_month()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        weekday_row = QHBoxLayout()
        weekday_row.setSpacing(2)
        for i, label_text in enumerate(_WEEKDAY_LABELS):
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = _COLOR_WEEKEND_TEXT if i in (0, 6) else "#8E8E93"
            lbl.setStyleSheet(
                f"color: {color}; font-size: 10px; font-weight: 800; "
                "font-family: monospace; background: transparent;"
            )
            weekday_row.addWidget(lbl)
        layout.addLayout(weekday_row)

        grid = QGridLayout()
        grid.setSpacing(3)
        for row in range(_ROWS):
            for col in range(_COLS):
                btn = QPushButton("")
                btn.setFlat(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(32)
                btn.clicked.connect(lambda _checked=False, b=btn: self._on_cell_clicked(b))
                attach_press_feedback(btn)
                grid.addWidget(btn, row, col)
                self._day_buttons.append(btn)
        layout.addLayout(grid, stretch=1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

    def go_previous_month(self) -> None:
        self._shown_month -= 1
        if self._shown_month < 1:
            self._shown_month = 12
            self._shown_year -= 1
        self._render_month()
        self.pageChanged.emit(self._shown_year, self._shown_month)

    def go_next_month(self) -> None:
        self._shown_month += 1
        if self._shown_month > 12:
            self._shown_month = 1
            self._shown_year += 1
        self._render_month()
        self.pageChanged.emit(self._shown_year, self._shown_month)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _on_cell_clicked(self, btn: QPushButton) -> None:
        date = btn.property("cal_date")
        if isinstance(date, QDate):
            self.dateSelected.emit(date)

    def _render_month(self) -> None:
        first_of_month = QDate(self._shown_year, self._shown_month, 1)
        dow = first_of_month.dayOfWeek()  # Mon=1 .. Sun=7
        start_offset = 0 if dow == 7 else dow
        grid_start = first_of_month.addDays(-start_offset)

        today = QDate.currentDate()

        for i, btn in enumerate(self._day_buttons):
            d = grid_start.addDays(i)
            btn.setProperty("cal_date", d)
            btn.setText(str(d.day()))

            in_month = d.month() == self._shown_month
            is_future = self._max_date is not None and d > self._max_date
            is_selected = d == self._selected_date
            is_today = d == today
            is_weekend = d.dayOfWeek() in (6, 7)

            has_record = True
            if self._highlighted_dates is not None:
                has_record = d == today or d.toString("yyyy-MM-dd") in self._highlighted_dates

            btn.setEnabled(in_month and not is_future)
            btn.setStyleSheet(
                self._cell_style(in_month, is_future, is_selected, is_today, is_weekend, has_record)
            )

        can_next = True
        if self._max_date is not None:
            can_next = (self._shown_year, self._shown_month) < (today.year(), today.month())
        self.canNavigateNextChanged.emit(can_next)

    @staticmethod
    def _cell_style(in_month, is_future, is_selected, is_today, is_weekend, has_record) -> str:
        base = (
            "QPushButton { border: none; border-radius: 6px; "
            "font-family: monospace; font-size: 11px; }"
        )

        if not in_month or is_future:
            return base + (
                f" QPushButton {{ color: {_COLOR_OUTSIDE_MONTH_TEXT}; background: transparent; }}"
            )

        if is_selected:
            return base + (
                f" QPushButton {{ background-color: {_COLOR_SELECTED_BG}; "
                f"color: {_COLOR_SELECTED_TEXT}; font-weight: 800; }}"
                f" QPushButton:hover {{ background-color: {_COLOR_SELECTED_BG_HOVER}; }}"
            )

        if is_today:
            return base + (
                f" QPushButton {{ background: transparent; border: 1px solid {_COLOR_TODAY_BORDER}; "
                f"color: {_COLOR_TODAY_TEXT}; font-weight: 800; }}"
                f" QPushButton:hover {{ background-color: {_COLOR_CELL_HOVER_BG}; }}"
            )

        if not has_record:
            color = _COLOR_NO_RECORD_TEXT
        elif is_weekend:
            color = _COLOR_WEEKEND_TEXT
        else:
            color = _COLOR_NORMAL_TEXT

        return base + (
            f" QPushButton {{ background: transparent; color: {color}; font-weight: 600; }}"
            f" QPushButton:hover {{ background-color: {_COLOR_CELL_HOVER_BG}; }}"
        )