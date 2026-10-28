""""Shared custom-painted pill/badge widget used across board tables and verification cards."""

from typing import Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from src.ui.theme import Colors, Spacing


class PillWidget(QWidget):
    """Rounded pill/badge widget with soft borders and optional gold flash animation."""

    _V_PADDING = Spacing.SM
    _H_PADDING = 14
    _BORDER_WIDTH = 1.2

    def __init__(
        self,
        text: str,
        bg_color: QColor,
        text_color: QColor,
        border_color: Optional[QColor] = None,
        fixed_size: Optional[QSize] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._text = text
        self._bg_color = bg_color
        self._text_color = text_color
        self._border_color = border_color
        self._fixed_size = fixed_size
        self._highlight_alpha = 0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        label_font = QFont(self.font())
        label_font.setWeight(QFont.Weight.Medium)
        self.setFont(label_font)

        if fixed_size is not None:
            self.setFixedSize(fixed_size)

    def set_text(self, text: str) -> None:
        self._text = text
        if self._fixed_size is None:
            self.updateGeometry()
        self.update()

    def set_colors(self, bg_color: QColor, text_color: QColor, border_color: Optional[QColor] = None) -> None:
        self._bg_color = bg_color
        self._text_color = text_color
        self._border_color = border_color
        self.update()

    def set_highlight_alpha(self, alpha: int) -> None:
        self._highlight_alpha = max(0, min(255, int(alpha)))
        self.update()

    def _computed_pill_rect(self) -> QRectF:
        """FIXED THIS SESSION: pill width was never clamped against the
        widget's own actual width, unlike pill height (which already clamps
        via `min(self.height() - 4, natural_height)`). Every call site in
        attendance_board.py passes a `fixed_size` (e.g. QSize(84, 26) /
        QSize(112, 26)); with the current fixed vocabulary of status/category
        strings this didn't visibly overflow, but it was a real missing
        bounds check -- any future longer label would have drawn a rounded
        rect wider than the widget itself, which gets hard-clipped at the
        widget edge (turning the capsule into a flat-cut shape and
        potentially clipping the text). Now clamped the same way height is.
        """
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(self._text)
        natural_height = metrics.height() + self._V_PADDING
        pill_height = min(self.height() - 4, natural_height) if self.height() > 4 else natural_height
        natural_width = text_width + (self._H_PADDING * 2)
        pill_width = min(self.width(), natural_width) if self.width() > 0 else natural_width
        return QRectF(
            (self.width() - pill_width) / 2.0,
            (self.height() - pill_height) / 2.0,
            pill_width,
            pill_height,
        )

    def sizeHint(self) -> QSize:
        if self._fixed_size is not None:
            return self._fixed_size
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(self._text)
        width = text_width + (self._H_PADDING * 2)
        height = metrics.height() + self._V_PADDING
        return QSize(width, height)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pill_rect = self._computed_pill_rect()
        radius = pill_rect.height() / 2.0

        if self._border_color is not None:
            painter.setPen(QPen(self._border_color, self._BORDER_WIDTH))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(pill_rect, radius, radius)

        if self._highlight_alpha > 0:
            overlay = QColor(Colors.ACCENT_GOLD)
            overlay.setAlpha(self._highlight_alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(overlay)
            painter.drawRoundedRect(pill_rect, radius, radius)

        painter.setPen(self._text_color)
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()