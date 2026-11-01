"""Non-blocking, floating toast notifications matching the Obsidian Gold brand theme."""

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QTimer,
    Qt,
)
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from src.ui.theme import Colors, Radius, Spacing, Typography
from src.utils.icon_helper import IconHelper

_SLIDE_IN_MS = 280
_SLIDE_OUT_MS = 220
_TOAST_TOP_MARGIN = Spacing.LG  # 24px grid alignment
_MAX_WIDTH_MARGIN = 80


class ToastNotification(QFrame):
    """Floating feedback toast notification with smooth entrance/exit animations, hover pause, and direct click dismiss."""

    _KIND_MAP = {
        "success": (Colors.TOAST_SUCCESS_BG, Colors.TOAST_SUCCESS_BORDER, Colors.TOAST_SUCCESS_ICON, "check-circle"),
        "error": (Colors.TOAST_ERROR_BG, Colors.TOAST_ERROR_BORDER, Colors.TOAST_ERROR_ICON, "alert-triangle"),
        "info": (Colors.TOAST_INFO_BG, Colors.TOAST_INFO_BORDER, Colors.TOAST_INFO_ICON, "info"),
    }

    def __init__(self, message: str, parent: QWidget, kind: str = "success", duration_ms: int = 2600):
        # Anchor to top-level window if available to prevent child container clipping
        target_parent = parent.window() if parent is not None else parent
        super().__init__(target_parent)

        self.setObjectName("toastFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        bg, border, text_color, icon_name = self._KIND_MAP.get(kind, self._KIND_MAP["info"])

        # Translucent glass elevation matching Design Tokens
        self.setStyleSheet(
            f"QFrame#toastFrame {{ "
            f"background-color: {bg}; "
            f"border: 1px solid {border}; "
            f"border-radius: {Radius.CARD}px; "
            f"}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.SM + 2, Spacing.LG, Spacing.SM + 2)
        layout.setSpacing(Spacing.SM)

        icon_label = QLabel()
        icon_label.setPixmap(IconHelper.get_pixmap(icon_name, color=text_color, size=18))
        icon_label.setFixedSize(18, 18)
        icon_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        # BODY_STACK is a fully-quoted font-family list with fallbacks, matching theme.qss
        self._message_label = QLabel(message)
        self._message_label.setStyleSheet(
            f"color: {text_color}; font-size: 12px; font-weight: 700; "
            f"font-family: {Typography.BODY_STACK}; background: transparent; border: none;"
        )
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label, stretch=1)

        max_width = 420
        if target_parent is not None and target_parent.width() > 0:
            max_width = max(240, min(max_width, target_parent.width() - _MAX_WIDTH_MARGIN))
        self.setMaximumWidth(max_width)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self.adjustSize()

        self._duration_ms = duration_ms
        self._remaining_ms = duration_ms

        # Animation references retained as instance attributes to prevent Python GC cleanup
        self._slide_in_anim: Optional[QPropertyAnimation] = None
        self._fade_in_anim: Optional[QPropertyAnimation] = None
        self._slide_out_anim: Optional[QPropertyAnimation] = None
        self._fade_out_anim: Optional[QPropertyAnimation] = None

        self._enter_group: Optional[QParallelAnimationGroup] = None
        self._exit_group: Optional[QParallelAnimationGroup] = None
        self._auto_dismiss_timer: Optional[QTimer] = None
        self._is_dismissing = False

    def show_animated(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            self.show()
            return

        self.adjustSize()
        target_x = (parent.width() - self.width()) // 2
        start_pos = QPoint(target_x, -self.height())
        end_pos = QPoint(target_x, _TOAST_TOP_MARGIN)

        self.move(start_pos)
        self._opacity_effect.setOpacity(0.0)
        self.show()
        self.raise_()

        # Retain explicit Python references to prevent garbage collection
        self._slide_in_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_in_anim.setDuration(_SLIDE_IN_MS)
        self._slide_in_anim.setStartValue(start_pos)
        self._slide_in_anim.setEndValue(end_pos)
        self._slide_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_in_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_in_anim.setDuration(_SLIDE_IN_MS)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._enter_group = QParallelAnimationGroup(self)
        self._enter_group.addAnimation(self._slide_in_anim)
        self._enter_group.addAnimation(self._fade_in_anim)
        self._enter_group.start()

        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self._dismiss)
        self._auto_dismiss_timer.start(self._duration_ms)

    def enterEvent(self, event) -> None:
        """Pauses auto-dismiss timer on mouse hover."""
        super().enterEvent(event)
        if self._auto_dismiss_timer is not None and self._auto_dismiss_timer.isActive():
            self._remaining_ms = max(500, self._auto_dismiss_timer.remainingTime())
            self._auto_dismiss_timer.stop()

    def leaveEvent(self, event) -> None:
        """Resumes auto-dismiss timer on hover exit using stored remaining time."""
        super().leaveEvent(event)
        if not self._is_dismissing and self._auto_dismiss_timer is not None:
            self._auto_dismiss_timer.start(self._remaining_ms)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Triggers immediate slide-out dismiss on click."""
        super().mousePressEvent(event)
        self.dismiss_immediately()

    def dismiss_immediately(self) -> None:
        if self._auto_dismiss_timer is not None:
            self._auto_dismiss_timer.stop()
        self._dismiss()

    def _dismiss(self) -> None:
        if self._is_dismissing:
            return
        self._is_dismissing = True

        if self._enter_group is not None:
            self._enter_group.stop()

        parent = self.parentWidget()
        if parent is None:
            self.deleteLater()
            return

        current_pos = self.pos()
        end_pos = QPoint(current_pos.x(), -self.height())

        # Retain explicit Python references to prevent garbage collection
        self._slide_out_anim = QPropertyAnimation(self, b"pos", self)
        self._slide_out_anim.setDuration(_SLIDE_OUT_MS)
        self._slide_out_anim.setStartValue(current_pos)
        self._slide_out_anim.setEndValue(end_pos)
        self._slide_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        self._fade_out_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_out_anim.setDuration(_SLIDE_OUT_MS)
        self._fade_out_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        self._exit_group = QParallelAnimationGroup(self)
        self._exit_group.addAnimation(self._slide_out_anim)
        self._exit_group.addAnimation(self._fade_out_anim)
        self._exit_group.finished.connect(self.deleteLater)
        self._exit_group.start()


def show_toast(parent: QWidget, message: str, kind: str = "success", duration_ms: int = 2600) -> ToastNotification:
    toast = ToastNotification(message, parent, kind=kind, duration_ms=duration_ms)
    toast.show_animated()
    return toast