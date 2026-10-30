"""Admin Login Authentication Dialog Modal."""

import logging
import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QPixmap
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
from src.services.auth_service import AuthService
from src.ui.theme import Colors, ObjectNames
from src.utils.icon_helper import IconHelper

logger = logging.getLogger(__name__)


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent.parent.parent.parent


class _PasswordLineEdit(QLineEdit):
    """Custom password input that detects Caps-Lock status."""

    def __init__(self, caps_label: QLabel, parent=None):
        super().__init__(parent)
        self.caps_label = caps_label
        self.setEchoMode(QLineEdit.EchoMode.Password)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self._check_caps()
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        self._check_caps()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self.caps_label.setVisible(False)
        super().focusOutEvent(event)

    def _check_caps(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                is_caps = bool(ctypes.windll.user32.GetKeyState(0x14) & 1)
                self.caps_label.setVisible(is_caps)
                return
            except Exception:
                pass
        self.caps_label.setVisible(False)


class AdminAuthDialog(QDialog):
    """Modal dialog prompting for admin username and password authentication."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.auth_service = AuthService(db_manager)
        self.authenticated_admin = None

        self.setWindowTitle("Administrator Authentication")
        self.setMinimumWidth(400)
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

        logo_path = _get_base_dir() / "assets" / "images" / "logo.png"
        if logo_path.exists():
            lbl_logo = QLabel()
            lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(str(logo_path)).scaled(
                48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pix)
            layout.addWidget(lbl_logo)

        lbl_title = QLabel("ADMINISTRATOR CONSOLE")
        lbl_title.setStyleSheet(f"color: {Colors.ACCENT_DARK}; font-size: 15px; font-weight: 800; letter-spacing: 0.6px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_sub = QLabel("Editorial Year 2026-2027 • Authentication Required")
        lbl_sub.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Username (e.g., admin)")
        self.txt_username.returnPressed.connect(self._handle_login)

        self.lbl_caps = QLabel("Caps Lock is ON")
        self.lbl_caps.setStyleSheet(f"color: {Colors.DANGER_SOLID}; font-size: 11px; font-weight: 600;")
        self.lbl_caps.setVisible(False)

        self.txt_password = _PasswordLineEdit(self.lbl_caps)
        self.txt_password.setPlaceholderText("Password")
        self.txt_password.returnPressed.connect(self._handle_login)

        lbl_user_label = QLabel("Username:")
        lbl_user_label.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_pass_label = QLabel("Password:")
        lbl_pass_label.setObjectName(ObjectNames.TEXT_SECONDARY)

        form_layout.addRow(lbl_user_label, self.txt_username)
        form_layout.addRow(lbl_pass_label, self.txt_password)
        form_layout.addRow("", self.lbl_caps)
        layout.addLayout(form_layout)

        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName(ObjectNames.FORM_ERROR_LABEL)
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_error)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_login = QPushButton("Authenticate")
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setObjectName(ObjectNames.BTN_PRIMARY)
        self.btn_login.setIcon(IconHelper.get_icon("shield", color="#FBFBFE"))
        self.btn_login.clicked.connect(self._handle_login)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.txt_username.setFocus()

    def _handle_login(self) -> None:
        username = self.txt_username.text().strip()
        password = self.txt_password.text()

        if not username or not password:
            self.lbl_error.setText("Please enter both username and password.")
            return

        self.btn_login.setEnabled(False)
        try:
            admin = self.auth_service.authenticate(username, password)
            self.authenticated_admin = admin
            self.accept()
        except AuthenticationError as e:
            self.lbl_error.setText(str(e))
            self.txt_password.clear()
            self.txt_password.setFocus()
        except Exception:
            logger.exception("Unexpected error during admin authentication for username=%r", username)
            self.lbl_error.setText("An unexpected error occurred. Please try again.")
            self.txt_password.clear()
            self.txt_password.setFocus()
        finally:
            self.btn_login.setEnabled(True)


AdminLoginDialog = AdminAuthDialog
