""""Themed modal overlays for Guest Visitor registration, manual ID entry, and action confirmation."""

from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.exceptions import ValidationError
from src.ui.components.animations import attach_press_feedback, fade_in_widget
from src.ui.theme import Colors, ObjectNames, Radius, Spacing, Typography
from src.utils.validators import validate_person_name, validate_student_id_format


class _BaseCountdownDialog(QDialog):
    """Base modal dialog with styled container and auto-close countdown progress bar."""

    def __init__(self, timeout_seconds: int = 20, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setObjectName("baseCountdownDialog")

        self.timeout_seconds = timeout_seconds
        self.remaining_seconds = timeout_seconds
        self._fade_anim = None

        # 1-Second Interval Timer for Label Counter
        self.counter_timer = QTimer(self)
        self.counter_timer.setInterval(1000)
        self.counter_timer.timeout.connect(self._on_counter_tick)

        # Smooth Progress Bar Indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(1000)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setObjectName("modalProgressBar")

        # Single Continuous 60 FPS Linear Animation
        self._progress_anim = QPropertyAnimation(self.progress_bar, b"value", self)
        self._progress_anim.setDuration(timeout_seconds * 1000)
        self._progress_anim.setStartValue(1000)
        self._progress_anim.setEndValue(0)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.Linear)
        self._progress_anim.finished.connect(self.reject)

        self.lbl_countdown = QLabel(f"Auto-closing in {timeout_seconds}s")
        self.lbl_countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_countdown.setObjectName(ObjectNames.TEXT_MUTED)

    def start_countdown(self) -> None:
        """Starts the countdown timer and smooth progress animation simultaneously."""
        self.counter_timer.start()
        self._progress_anim.start()

    def _on_counter_tick(self) -> None:
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.counter_timer.stop()
        else:
            self.lbl_countdown.setText(f"Auto-closing in {self.remaining_seconds}s")

    def done(self, r: int) -> None:
        if self.counter_timer.isActive():
            self.counter_timer.stop()
        if self._progress_anim.state() == QPropertyAnimation.State.Running:
            self._progress_anim.stop()
        super().done(r)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fade_anim = fade_in_widget(self)


class TimeOutConfirmationDialog(_BaseCountdownDialog):
    """Modal dialog prompting active staffer or visitor for explicit Time-Out confirmation."""

    def __init__(self, full_name: str, role_or_type: str, time_in_str: str, parent: Optional[QWidget] = None):
        super().__init__(timeout_seconds=20, parent=parent)

        self.setWindowTitle("Confirm Time-Out")
        self._init_ui(full_name, role_or_type, time_in_str)
        self.start_countdown()

    def _init_ui(self, full_name: str, role_or_type: str, time_in_str: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        lbl_header = QLabel("TIME-OUT CONFIRMATION")
        lbl_header.setObjectName("dialogHeaderDanger")
        lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_header)

        lbl_name = QLabel(full_name)
        lbl_name.setObjectName(ObjectNames.DIALOG_SUBJECT_NAME)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_name.setWordWrap(True)
        layout.addWidget(lbl_name)

        lbl_role = QLabel(f"Role / Type: {role_or_type}")
        lbl_role.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_role)

        lbl_time = QLabel(f"Recorded Time-In: {time_in_str}")
        lbl_time.setObjectName(ObjectNames.DIALOG_EMPHASIS_TEXT)
        lbl_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_time)

        # Button Layout HIG Standards: [Cancel (Secondary)] [Confirm (Primary/Danger)]
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        btn_cancel = QPushButton("Cancel (Esc)")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)
        attach_press_feedback(btn_cancel)

        btn_confirm = QPushButton("Confirm Time-Out (Enter)")
        btn_confirm.setFixedHeight(40)
        btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_confirm.setObjectName(ObjectNames.BTN_DANGER_SOLID)
        btn_confirm.clicked.connect(self.accept)
        attach_press_feedback(btn_confirm)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_confirm)
        layout.addLayout(btn_layout)

        layout.addSpacing(Spacing.XS)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_countdown)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Y):
            self.accept()
        elif key in (Qt.Key.Key_Escape, Qt.Key.Key_N):
            self.reject()
        else:
            super().keyPressEvent(event)


class GuestVisitorNameDialog(_BaseCountdownDialog):
    """Modal dialog asking an unregistered guest student to input their full legal name."""

    def __init__(self, student_id_no: str, parent: Optional[QWidget] = None):
        super().__init__(timeout_seconds=30, parent=parent)
        self.entered_name = ""

        self.setWindowTitle("Guest Visitor Registration")
        self._init_ui(student_id_no)
        self.start_countdown()

    def _init_ui(self, student_id_no: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        lbl_header = QLabel("GUEST VISITOR CHECK-IN")
        lbl_header.setObjectName("dialogHeaderInfo")
        lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_header)

        lbl_id = QLabel(f"Student ID No: {student_id_no}")
        lbl_id.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_id.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_id)

        self.txt_name = QLineEdit()
        self.txt_name.setFixedHeight(40)
        self.txt_name.setPlaceholderText("Enter visitor full legal name...")
        self.txt_name.returnPressed.connect(self._handle_submit)
        layout.addWidget(self.txt_name)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName(ObjectNames.FORM_ERROR_LABEL)
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_error)

        # Button Layout HIG Standards: [Cancel (Secondary)] [Confirm (Primary)]
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)
        attach_press_feedback(btn_cancel)

        btn_submit = QPushButton("Confirm Check-In")
        btn_submit.setFixedHeight(40)
        btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_submit.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_submit.clicked.connect(self._handle_submit)
        attach_press_feedback(btn_submit)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_submit)
        layout.addLayout(btn_layout)

        layout.addSpacing(Spacing.XS)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_countdown)

        self.txt_name.setFocus()

    def _handle_submit(self) -> None:
        raw_name = self.txt_name.text().strip()
        if not raw_name:
            self.lbl_error.setText("Please enter visitor full name.")
            return

        try:
            cleaned_name = validate_person_name(raw_name)
        except ValidationError as e:
            self.lbl_error.setText(str(e))
            return

        self.entered_name = cleaned_name
        self.accept()


class ManualIdEntryDialog(_BaseCountdownDialog):
    """Modal dialog allowing manual Student ID entry."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(timeout_seconds=30, parent=parent)
        self.entered_id = ""

        self.setWindowTitle("Manual Attendance Entry")
        self._init_ui()
        self.start_countdown()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)

        lbl_header = QLabel("MANUAL STUDENT ID ENTRY")
        lbl_header.setObjectName("dialogHeaderInfo")
        lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_header)

        lbl_instruct = QLabel("Enter student ID number (e.g. 261-00105):")
        lbl_instruct.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_instruct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_instruct)

        self.txt_id = QLineEdit()
        self.txt_id.setFixedHeight(40)
        self.txt_id.setPlaceholderText("Format: XXX-XXXXX")
        self.txt_id.returnPressed.connect(self._handle_submit)
        layout.addWidget(self.txt_id)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName(ObjectNames.FORM_ERROR_LABEL)
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_error)

        # Button Layout HIG Standards: [Cancel (Secondary)] [Submit (Primary)]
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)
        attach_press_feedback(btn_cancel)

        btn_submit = QPushButton("Submit ID")
        btn_submit.setFixedHeight(40)
        btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_submit.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_submit.clicked.connect(self._handle_submit)
        attach_press_feedback(btn_submit)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_submit)
        layout.addLayout(btn_layout)

        layout.addSpacing(Spacing.XS)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.lbl_countdown)

        self.txt_id.setFocus()

    def _handle_submit(self) -> None:
        raw_id = self.txt_id.text().strip()
        if not raw_id:
            self.lbl_error.setText("Please enter a student ID number.")
            return

        try:
            cleaned_id = validate_student_id_format(raw_id)
        except ValidationError as e:
            self.lbl_error.setText(str(e))
            return

        self.entered_id = cleaned_id
        self.accept()