""""Lightweight toast-style notification widget with Lucide iconography for non-disruptive feedback."""

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QTimer,
    Qt,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from src.utils.icon_helper import IconHelper

_SLIDE_IN_MS = 280
_SLIDE_OUT_MS = 220
_TOAST_TOP_MARGIN = 20
_MAX_WIDTH_MARGIN = 80  # keeps the toast from touching the parent's edges


class ToastNotification(QFrame):
    """A transient, auto-dismissing notification banner matching GP Brand guidelines."""

    # FIXED THIS SESSION: "success" now uses the same green as theme.py's
    # STATUS_OPEN/SUCCESS_BG (fixed earlier this session) instead of the old
    # blue, which coincidentally matched the COMPLETED/info color and made
    # "success" and "informational" toasts look like the same semantic.
    _STYLE_BY_KIND = {
        "success": (
            "QFrame#toastFrame { background-color: #113B24; border: 1px solid #1E5A38; border-radius: 8px; }",
            "#8FE3B0",
            "check-circle",
        ),
        "error": (
            "QFrame#toastFrame { background-color: #58111A; border: 1px solid #7A1B28; border-radius: 8px; }",
            "#FF99A4",
            "alert-circle",
        ),
        "info": (
            "QFrame#toastFrame { background-color: #2E2512; border: 1px solid rgba(218, 165, 32, 0.45); border-radius: 8px; }",
            "#E5B842",
            "info",
        ),
    }

    def __init__(self, message: str, parent: QWidget, kind: str = "success", duration_ms: int = 2600):
        super().__init__(parent)
        self.setObjectName("toastFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        style, text_color, icon_name = self._STYLE_BY_KIND.get(kind, self._STYLE_BY_KIND["info"])
        self.setStyleSheet(style)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 20, 12)
        layout.setSpacing(10)

        icon_label = QLabel()
        icon_label.setPixmap(IconHelper.get_pixmap(icon_name, color=text_color, size=18))
        icon_label.setFixedSize(18, 18)
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        self._message_label = QLabel(message)
        self._message_label.setStyleSheet(
            f"color: {text_color}; font-size: 13px; font-weight: 700; background: transparent;"
        )
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label, stretch=1)

        max_width = 420
        if parent is not None and parent.width() > 0:
            max_width = max(240, min(max_width, parent.width() - _MAX_WIDTH_MARGIN))
        self.setMaximumWidth(max_width)

        # FIXED THIS SESSION: toasts previously only slid; now paired with an
        # opacity fade for a softer, less mechanical entrance/exit.
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self.adjustSize()

        self._duration_ms = duration_ms
        self._enter_group = None
        self._exit_group = None
        self._auto_dismiss_timer = None
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

        slide_in = QPropertyAnimation(self, b"pos", self)
        slide_in.setDuration(_SLIDE_IN_MS)
        slide_in.setStartValue(start_pos)
        slide_in.setEndValue(end_pos)
        slide_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade_in = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade_in.setDuration(_SLIDE_IN_MS)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._enter_group = QParallelAnimationGroup(self)
        self._enter_group.addAnimation(slide_in)
        self._enter_group.addAnimation(fade_in)
        self._enter_group.start()

        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self._dismiss)
        self._auto_dismiss_timer.start(self._duration_ms)

    def dismiss_immediately(self) -> None:
        if self._auto_dismiss_timer is not None:
            self._auto_dismiss_timer.stop()
        self._dismiss()

    def _dismiss(self) -> None:
        if self._is_dismissing:
            return
        self._is_dismissing = True

        # FIXED THIS SESSION: if dismiss is triggered while the entrance
        # animation is still running (e.g. a new scan replaces the toast
        # almost immediately), the old code would start a second
        # QPropertyAnimation on the same `pos` property concurrently with
        # the still-running entrance animation, causing visible jitter.
        # Stopping the entrance group first prevents that collision.
        if self._enter_group is not None:
            self._enter_group.stop()

        parent = self.parentWidget()
        if parent is None:
            self.deleteLater()
            return

        current_pos = self.pos()
        end_pos = QPoint(current_pos.x(), -self.height())

        slide_out = QPropertyAnimation(self, b"pos", self)
        slide_out.setDuration(_SLIDE_OUT_MS)
        slide_out.setStartValue(current_pos)
        slide_out.setEndValue(end_pos)
        slide_out.setEasingCurve(QEasingCurve.Type.InCubic)

        fade_out = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        fade_out.setDuration(_SLIDE_OUT_MS)
        fade_out.setStartValue(self._opacity_effect.opacity())
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        self._exit_group = QParallelAnimationGroup(self)
        self._exit_group.addAnimation(slide_out)
        self._exit_group.addAnimation(fade_out)
        self._exit_group.finished.connect(self.deleteLater)
        self._exit_group.start()


def show_toast(parent: QWidget, message: str, kind: str = "success", duration_ms: int = 2600) -> ToastNotification:
    toast = ToastNotification(message, parent, kind=kind, duration_ms=duration_ms)
    toast.show_animated()
    return toast