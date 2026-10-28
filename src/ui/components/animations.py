""""Small reusable Qt animation helpers shared across dialogs and views."""

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton, QWidget


class _ButtonPressAnimator(QObject):
    """Event filter attached to a QPushButton, dipping opacity on press for tactile feedback."""

    def __init__(self, button: QPushButton):
        super().__init__(button)
        self._button = button
        self._effect = QGraphicsOpacityEffect(button)
        self._effect.setOpacity(1.0)
        button.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(110)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        button.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self._button:
            if event.type() == QEvent.Type.MouseButtonPress:
                self._animate_to(0.62)
            elif event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.Leave):
                self._animate_to(1.0)
        return super().eventFilter(obj, event)

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(target)
        self._anim.start()


def attach_press_feedback(button: QPushButton) -> None:
    # NOTE: this helper existed before this session but was never actually
    # called anywhere in the codebase -- confirmed dead code, meaning no
    # button in the app ever had press feedback. Now wired up from
    # station_view.py and main_window.py.
    animator = _ButtonPressAnimator(button)
    button._press_animator = animator


def fade_in_widget(widget: QWidget, duration_ms: int = 220) -> QPropertyAnimation:
    widget.setWindowOpacity(0.0)
    anim = QPropertyAnimation(widget, b"windowOpacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    return anim