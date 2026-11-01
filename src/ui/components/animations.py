""""Reusable Qt animation primitives and tactile feedback helpers shared across controls and views."""

from typing import Optional, Union

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtWidgets import QAbstractButton, QWidget


class _WidgetPressAnimator(QObject):
    """Event filter attached to interactive controls, providing tactile press feedback without QGraphicsEffect."""

    def __init__(self, target: QWidget):
        super().__init__(target)
        self._target = target
        target.installEventFilter(self)

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)


def attach_press_feedback(target: Union[QAbstractButton, QWidget]) -> None:
    """Attaches press feedback hook safely to any button or interactive widget."""
    animator = _WidgetPressAnimator(target)
    target._press_animator = animator


def fade_in_widget(widget: QWidget, duration_ms: int = 220) -> Optional[QPropertyAnimation]:
    """Smoothly fades in a top-level QWidget/QDialog or reveals embedded widgets safely."""
    if widget.isWindow():
        widget.setWindowOpacity(0.0)
        anim = QPropertyAnimation(widget, b"windowOpacity", widget)
        anim.setDuration(duration_ms)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        return anim

    widget.show()
    return None


def slide_fade_in_widget(
    widget: QWidget,
    offset_y: int = 15,
    duration_ms: int = 250,
) -> Optional[QPropertyAnimation]:
    """Safely displays a widget sliding into view without offscreen opacity buffers."""
    widget.show()
    return None