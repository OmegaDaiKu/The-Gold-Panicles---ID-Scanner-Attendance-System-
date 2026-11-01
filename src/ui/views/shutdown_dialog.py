"""
Restricted Application Shutdown Confirmation Modal requiring administrator authorization.
"""

import logging

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.exceptions import AuthenticationError
from src.database.connection import DatabaseConnectionManager
from src.services.auth_service import AuthService
from src.ui.components.animations import attach_press_feedback, fade_in_widget
from src.ui.theme import Colors, ObjectNames, Radius, Spacing
from src.utils.icon_helper import IconHelper

logger = logging.getLogger(__name__)


class ShutdownAuthDialog(QDialog):
    """Modal dialog prompting for admin credentials before allowing kiosk shutdown."""

    def __init__(self, db_manager: DatabaseConnectionManager, parent=None):
        super().__init__(parent)
        self.auth_service = AuthService(db_manager)
        self.authorized = False
        self._fade_anim = None

        self.setWindowTitle("Authorized Shutdown Required")
        self.setMinimumWidth(400)
        self.setModal(True)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.SUPER}px;
            }}
            """
        )

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)
        layout.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.LG)

        # Security Alert Header
        lbl_header = QLabel("RESTRICTED SYSTEM SHUTDOWN")
        lbl_header.setStyleSheet(
            f"color: {Colors.DANGER_SOLID}; font-size: 14px; font-weight: 800; letter-spacing: 0.8px; background: transparent;"
        )
        lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_header)

        lbl_sub = QLabel("Administrator password required to close the kiosk application.")
        lbl_sub.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        layout.addSpacing(4)

        # Input Form Area
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(Spacing.XS)

        lbl_pass_label = QLabel("ADMINISTRATOR PASSWORD")
        lbl_pass_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9.5px; font-weight: 800; letter-spacing: 0.8px; font-family: monospace;"
        )
        input_layout.addWidget(lbl_pass_label)

        self.txt_password = QLineEdit()
        self.txt_password.setObjectName(ObjectNames.GP_SUPER_INPUT)
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Enter Admin Password...")
        self.txt_password.addAction(
            IconHelper.get_icon("lock", color=Colors.DANGER_SOLID, size=16),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.txt_password.returnPressed.connect(self._handle_auth)
        input_layout.addWidget(self.txt_password)

        layout.addWidget(input_container)

        # Error Label
        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName(ObjectNames.FORM_ERROR_LABEL)
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setWordWrap(True)
        layout.addWidget(self.lbl_error)

        layout.addSpacing(4)

        # Actions Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        self.btn_shutdown = QPushButton("Authorize Shutdown")
        self.btn_shutdown.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shutdown.setObjectName(ObjectNames.BTN_DANGER_SOLID)
        self.btn_shutdown.setIcon(IconHelper.get_icon("log-out", color="#FFFFFF", size=16))
        self.btn_shutdown.clicked.connect(self._handle_auth)
        attach_press_feedback(self.btn_shutdown)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)
        attach_press_feedback(btn_cancel)

        btn_layout.addWidget(self.btn_shutdown)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.txt_password.setFocus()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fade_anim = fade_in_widget(self)

    def _shake_dialog(self) -> None:
        """Visual shake animation indicating unauthorized exit attempt."""
        pos = self.pos()
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim.setKeyValueAt(0.0, pos)
        anim.setKeyValueAt(0.2, pos + QPoint(-10, 0))
        anim.setKeyValueAt(0.4, pos + QPoint(10, 0))
        anim.setKeyValueAt(0.6, pos + QPoint(-6, 0))
        anim.setKeyValueAt(0.8, pos + QPoint(6, 0))
        anim.setKeyValueAt(1.0, pos)

        anim.start()

    def _handle_auth(self) -> None:
        password = self.txt_password.text().strip()

        if not password:
            self.lbl_error.setText("Please enter the administrator password.")
            self._shake_dialog()
            return

        self.btn_shutdown.setEnabled(False)
        try:
            self.auth_service.authenticate(password)
            self.authorized = True
            self.accept()
        except AuthenticationError as e:
            self.lbl_error.setText(str(e))
            self.txt_password.clear()
            self.txt_password.setFocus()
            self._shake_dialog()
        except Exception:
            logger.exception("Unexpected error during shutdown authorization")
            self.lbl_error.setText("An unexpected error occurred. Please try again.")
            self.txt_password.clear()
            self.txt_password.setFocus()
            self._shake_dialog()
        finally:
            self.btn_shutdown.setEnabled(True)