"""Restricted Application Shutdown Confirmation Modal requiring administrator authorization."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.core.exceptions import AuthenticationError
from src.database.connection import DatabaseConnectionManager
from src.services.auth_service import AuthService
from src.ui.theme import Colors, ObjectNames
from src.utils.icon_helper import IconHelper

logger = logging.getLogger(__name__)


class ShutdownAuthDialog(QDialog):
    """Modal dialog prompting for admin credentials before allowing kiosk shutdown."""

    def __init__(self, db_manager: DatabaseConnectionManager, parent=None):
        super().__init__(parent)
        self.auth_service = AuthService(db_manager)
        self.authorized = False

        self.setWindowTitle("Authorized Shutdown Required")
        self.setMinimumWidth(380)
        self.setModal(True)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {Colors.BACKGROUND};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
            }}
            """
        )

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 24)

        lbl_header = QLabel("RESTRICTED SYSTEM SHUTDOWN")
        lbl_header.setStyleSheet(f"color: {Colors.DANGER_SOLID}; font-size: 13px; font-weight: 800; letter-spacing: 0.8px;")
        lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_header)

        lbl_sub = QLabel("Administrator credentials required to close the application.")
        lbl_sub.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Admin Username")

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Admin Password")
        self.txt_password.returnPressed.connect(self._handle_auth)

        lbl_user = QLabel("Username:")
        lbl_user.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_pass = QLabel("Password:")
        lbl_pass.setObjectName(ObjectNames.TEXT_SECONDARY)

        form_layout.addRow(lbl_user, self.txt_username)
        form_layout.addRow(lbl_pass, self.txt_password)
        layout.addLayout(form_layout)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName(ObjectNames.FORM_ERROR_LABEL)
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_error)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_shutdown = QPushButton("Authorize Shutdown")
        self.btn_shutdown.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_shutdown.setObjectName(ObjectNames.BTN_DANGER_SOLID)
        self.btn_shutdown.setIcon(IconHelper.get_icon("log-out", color="#FFFFFF"))
        self.btn_shutdown.clicked.connect(self._handle_auth)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_shutdown)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.txt_username.setFocus()

    def _handle_auth(self) -> None:
        username = self.txt_username.text().strip()
        password = self.txt_password.text()

        if not username or not password:
            self.lbl_error.setText("Please enter username and password.")
            return

        self.btn_shutdown.setEnabled(False)
        try:
            self.auth_service.authenticate(username, password)
            self.authorized = True
            self.accept()
        except AuthenticationError as e:
            self.lbl_error.setText(str(e))
            self.txt_password.clear()
            self.txt_password.setFocus()
        except Exception:
            logger.exception("Unexpected error during shutdown authorization for username=%r", username)
            self.lbl_error.setText("An unexpected error occurred. Please try again.")
            self.txt_password.clear()
            self.txt_password.setFocus()
        finally:
            self.btn_shutdown.setEnabled(True)
