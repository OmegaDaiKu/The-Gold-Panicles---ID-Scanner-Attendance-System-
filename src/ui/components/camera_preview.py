"""Camera Preview Widget displaying live video feed, camera state, and active counts."""

from PySide6.QtCore import Qt, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme import Colors, ObjectNames, Radius, Spacing
from src.ui.widgets.pill_widget import PillWidget
from src.utils.icon_helper import IconHelper


class CameraPreviewWidget(QWidget):
    """Widget rendering live camera feed with aspect ratio preservation and status metrics."""

    _DEFAULT_BORDER_COLOR = QColor(Colors.BORDER)
    _SUCCESS_FLASH_COLOR = QColor(Colors.STATUS_OPEN)
    _FAILURE_FLASH_COLOR = QColor(Colors.DANGER_SOLID)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flash_anim = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        self.lbl_status = QLabel("INITIALIZING CAMERA...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setObjectName(ObjectNames.CAMERA_STATUS_LABEL)
        layout.addWidget(self.lbl_status)

        self.lbl_feed = QLabel("CONNECTING CAMERA...")
        self.lbl_feed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_feed.setMinimumSize(240, 150)
        self.lbl_feed.setObjectName(ObjectNames.CAMERA_FEED_LABEL)
        self._apply_feed_border_color(self._DEFAULT_BORDER_COLOR)
        layout.addWidget(self.lbl_feed, stretch=1)

        count_frame = QFrame()
        count_frame.setObjectName(ObjectNames.CAMERA_COUNT_FRAME)
        count_layout = QHBoxLayout(count_frame)
        count_layout.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        count_layout.setSpacing(Spacing.LG)

        duty_box = QHBoxLayout()
        duty_box.setSpacing(Spacing.SM)
        lbl_duty_icon = QLabel()
        duty_icon = IconHelper.get_icon("clock", color=Colors.TEXT_PRIMARY)
        lbl_duty_icon.setPixmap(duty_icon.pixmap(14, 14))
        self.duty_pill = PillWidget(
            text="Duty: 0",
            bg_color=QColor(Colors.CHIP_DUTY_BG),
            text_color=QColor(Colors.TEXT_PRIMARY),
            border_color=QColor(Colors.BORDER),
        )
        duty_box.addWidget(lbl_duty_icon)
        duty_box.addWidget(self.duty_pill)

        visitor_box = QHBoxLayout()
        visitor_box.setSpacing(Spacing.SM)
        lbl_visitor_icon = QLabel()
        visitor_icon = IconHelper.get_icon("users", color=Colors.TEXT_PRIMARY)
        lbl_visitor_icon.setPixmap(visitor_icon.pixmap(14, 14))
        self.visitor_pill = PillWidget(
            text="Visitors: 0",
            bg_color=QColor(Colors.CHIP_NEUTRAL_BG),
            text_color=QColor(Colors.TEXT_PRIMARY),
            border_color=QColor(Colors.BORDER),
        )
        visitor_box.addWidget(lbl_visitor_icon)
        visitor_box.addWidget(self.visitor_pill)

        count_layout.addLayout(duty_box)
        count_layout.addStretch()
        count_layout.addLayout(visitor_box)

        layout.addWidget(count_frame)

    def update_frame(self, q_img: QImage) -> None:
        """Scales video frame dynamically to label dimensions maintaining 4:3 aspect ratio."""
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(
            self.lbl_feed.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.lbl_feed.setPixmap(scaled_pixmap)

    def update_status(self, msg: str) -> None:
        """Updates camera connection or scan status display."""
        self.lbl_status.setText(msg)

    def update_counts(self, active_duty: int, guest_count: int) -> None:
        """Updates active duty staff and visitor count pill text."""
        self.duty_pill.set_text(f"Duty: {active_duty}")
        self.visitor_pill.set_text(f"Visitors: {guest_count}")

    def _apply_feed_border_color(self, color: QColor) -> None:
        """Repaints the camera feed label's border in the given color."""
        self.lbl_feed.setStyleSheet(f"""
            QLabel#{ObjectNames.CAMERA_FEED_LABEL} {{
                background-color: {Colors.BACKGROUND};
                border: 1.5px solid {color.name()};
                border-radius: {Radius.SM}px;
                color: {Colors.TEXT_MUTED};
                font-weight: 600;
                font-size: 12px;
            }}
        """)

    def _flash(self, color: QColor, duration_ms: int = 650) -> None:
        """Animates the camera feed's border from `color` back to its resting border color."""
        if self._flash_anim is not None:
            self._flash_anim.stop()

        anim = QVariantAnimation(self)
        anim.setStartValue(QColor(color))
        anim.setEndValue(QColor(self._DEFAULT_BORDER_COLOR))
        anim.setDuration(duration_ms)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._apply_feed_border_color)
        anim.finished.connect(lambda: self._apply_feed_border_color(self._DEFAULT_BORDER_COLOR))
        self._flash_anim = anim
        anim.start()

    def flash_success(self) -> None:
        """Briefly flashes the camera feed border green to confirm a scan was successfully processed."""
        self._flash(self._SUCCESS_FLASH_COLOR)

    def flash_failure(self) -> None:
        """Briefly flashes the camera feed border red to indicate a scan was rejected or invalid."""
        self._flash(self._FAILURE_FLASH_COLOR)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.lbl_feed.update()
