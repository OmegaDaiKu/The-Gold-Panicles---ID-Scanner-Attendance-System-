""""Shared custom-painted pill/badge widget used across board tables, visitor logs, and verification cards."""

from typing import Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from src.ui.theme import Colors, Radius, Spacing, Typography


class PillWidget(QWidget):
    """Rounded translucent status chip / badge widget with high-DPI vector precision and Apple HIG styling."""

    _V_PADDING = 3
    _H_PADDING = Spacing.SM
    _BORDER_WIDTH = 1.0

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
        self._text = text.upper()
        self._bg_color = bg_color
        self._text_color = text_color
        self._border_color = border_color
        self._fixed_size = fixed_size
        self._highlight_alpha = 0
        self._gold_color = Colors.parse_qcolor(Colors.ACCENT_GOLD)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        label_font = QFont(Typography.MONO_FAMILY, 9.5)
        label_font.setWeight(QFont.Weight.Bold)
        label_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self.setFont(label_font)

        if fixed_size is not None:
            self.setFixedSize(fixed_size)

    def set_text(self, text: str) -> None:
        self._text = text.upper()
        if self._fixed_size is None:
            self.updateGeometry()
        self.update()

    def set_colors(
        self,
        bg_color: QColor,
        text_color: QColor,
        border_color: Optional[QColor] = None,
    ) -> None:
        self._bg_color = bg_color
        self._text_color = text_color
        self._border_color = border_color
        self.update()

    def set_highlight_alpha(self, alpha: int) -> None:
        self._highlight_alpha = max(0, min(255, int(alpha)))
        self.update()

    def _computed_pill_rect(self) -> QRectF:
        """Calculates sub-pixel vector geometry for anti-aliased chip bounds with stroke padding."""
        offset = self._BORDER_WIDTH / 2.0
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(self._text)
        natural_height = metrics.height() + (self._V_PADDING * 2)

        available_w = max(0.0, float(self.width()) - (offset * 2.0))
        available_h = max(0.0, float(self.height()) - (offset * 2.0))

        natural_width = float(text_width + (self._H_PADDING * 2))
        pill_width = min(available_w, natural_width) if available_w > 0 else natural_width
        pill_height = min(available_h, float(natural_height)) if available_h > 0 else float(natural_height)

        x = (float(self.width()) - pill_width) / 2.0
        y = (float(self.height()) - pill_height) / 2.0

        return QRectF(x, y, pill_width, pill_height)

    def sizeHint(self) -> QSize:
        if self._fixed_size is not None:
            return self._fixed_size
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(self._text)
        width = text_width + (self._H_PADDING * 2) + 4
        height = metrics.height() + (self._V_PADDING * 2) + 2
        return QSize(width, height)

    def paintEvent(self, event) -> None:
        painter = QPainter()
        if not painter.begin(self):
            return

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            pill_rect = self._computed_pill_rect()
            radius = float(getattr(Radius, "CHIP", 6))

            # Background Surface & Pen Border
            if self._border_color is not None:
                painter.setPen(QPen(self._border_color, self._BORDER_WIDTH))
            else:
                painter.setPen(Qt.PenStyle.NoPen)

            painter.setBrush(self._bg_color)
            painter.drawRoundedRect(pill_rect, radius, radius)

            # Pulse Glow Overlay
            if self._highlight_alpha > 0:
                overlay = QColor(self._gold_color)
                overlay.setAlpha(self._highlight_alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(overlay)
                painter.drawRoundedRect(pill_rect, radius, radius)

            # Text Label
            painter.setFont(self.font())
            painter.setPen(self._text_color)
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, self._text)
        finally:
            painter.end()