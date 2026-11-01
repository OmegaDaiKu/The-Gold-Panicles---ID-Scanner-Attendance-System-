""""Hardware QR Scanner Status Viewport displaying scanner status and visual scan confirmation feedback."""

from typing import Optional

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.ui.theme import Colors, Radius, Spacing, Typography
from src.utils.icon_helper import IconHelper


class _StatusViewportCard(QFrame):
    """Custom-painted viewport frame supporting smooth 60 FPS border flash animations."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._border_color = Colors.parse_qcolor(Colors.BORDER)
        self._bg_color = Colors.parse_qcolor(Colors.SURFACE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_border_color(self, color: QColor) -> None:
        self._border_color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter()
        if not painter.begin(self):
            return

        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            radius = float(getattr(Radius, "CARD", 12))

            # Draw Surface Background
            painter.setBrush(self._bg_color)
            painter.setPen(QPen(self._border_color, 1.2))
            painter.drawRoundedRect(rect, radius, radius)
        finally:
            painter.end()


class CameraPreviewWidget(QWidget):
    """Viewport rendering hardware QR scanner state and 60 FPS vector flash feedback."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._flash_anim: Optional[QVariantAnimation] = None

        self._default_border_color = Colors.parse_qcolor(Colors.BORDER)
        self._success_flash_color = Colors.parse_qcolor(Colors.STATUS_IN)
        self._failure_flash_color = Colors.parse_qcolor(Colors.DANGER_SOLID)

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.viewport_card = _StatusViewportCard()
        self.viewport_card.setObjectName("scannerViewportCard")

        vp_layout = QHBoxLayout(self.viewport_card)
        vp_layout.setContentsMargins(Spacing.MD, Spacing.SM + 2, Spacing.MD, Spacing.SM + 2)
        vp_layout.setSpacing(Spacing.SM + 2)

        self.lbl_icon = QLabel()
        self.lbl_icon.setPixmap(IconHelper.get_pixmap("qr-code", color=Colors.ACCENT_GOLD, size=18))
        self.lbl_icon.setStyleSheet("background: transparent; border: none;")
        vp_layout.addWidget(self.lbl_icon, alignment=Qt.AlignmentFlag.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)

        self.lbl_status = QLabel("HARDWARE QR SCANNER READY")
        self.lbl_status.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-weight: 800; font-size: 11px; "
            f"font-family: {Typography.MONO_FAMILY}; letter-spacing: 0.6px; background: transparent; border: none;"
        )

        self.lbl_subtext = QLabel("USB / Barcode Reader Active")
        self.lbl_subtext.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent; border: none;"
        )

        text_box.addWidget(self.lbl_status)
        text_box.addWidget(self.lbl_subtext)
        vp_layout.addLayout(text_box, stretch=1)

        # Vector Status Dot
        self.pulse_dot = QLabel()
        self.pulse_dot.setFixedSize(10, 10)
        self.pulse_dot.setStyleSheet(
            f"background-color: {Colors.STATUS_IN}; border-radius: 5px; border: none;"
        )
        vp_layout.addWidget(self.pulse_dot, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.viewport_card)

    def update_frame(self, _image=None) -> None:
        pass

    def update_status(self, msg: str) -> None:
        self.lbl_status.setText(msg.upper())

    def update_counts(self, active_duty: int, guest_count: int) -> None:
        pass

    def _flash(self, color: QColor, duration_ms: int = 500) -> None:
        if self._flash_anim is not None:
            self._flash_anim.stop()

        anim = QVariantAnimation(self)
        anim.setStartValue(QColor(color))
        anim.setEndValue(QColor(self._default_border_color))
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _on_border_changed(val: QColor):
            if isinstance(val, QColor):
                self.viewport_card.set_border_color(val)

        anim.valueChanged.connect(_on_border_changed)
        anim.finished.connect(lambda: self.viewport_card.set_border_color(self._default_border_color))
        self._flash_anim = anim
        anim.start()

    def flash_success(self) -> None:
        self._flash(self._success_flash_color)

    def flash_failure(self) -> None:
        self._flash(self._failure_flash_color)