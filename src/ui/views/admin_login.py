"""
Admin Login Authentication Dialog Modal.
Provides administrator authentication to access management tools and system settings.
"""

import logging
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QKeyEvent, QPixmap
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
from src.services.auth_service import AuthService
from src.ui.components.animations import attach_press_feedback, fade_in_widget
from src.ui.theme import Colors, ObjectNames, Radius, Spacing, Typography
from src.utils.icon_helper import IconHelper

logger = logging.getLogger(__name__)


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent.parent.parent.parent


class _PasswordLineEdit(QLineEdit):
    """Custom password input that detects and displays Caps-Lock status."""

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
    """Modal dialog prompting for administrator password authentication."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.auth_service = AuthService(db_manager)
        self.authenticated_admin = None
        self._fade_anim = None

        self.setWindowTitle("Administrator Authentication")
        self.setMinimumWidth(420)
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

        # Brand Logo Header
        logo_path = _get_base_dir() / "assets" / "images" / "logo.png"
        if logo_path.exists():
            lbl_logo = QLabel()
            lbl_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(str(logo_path)).scaled(
                52, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pix)
            layout.addWidget(lbl_logo)

        # Title & Context Subtitle
        lbl_title = QLabel("ADMINISTRATOR CONSOLE")
        lbl_title.setStyleSheet(
            f"color: {Colors.ACCENT_GOLD}; font-size: 15px; font-weight: 800; letter-spacing: 0.8px; background: transparent;"
        )
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_sub = QLabel("Editorial Management • Master Authentication")
        lbl_sub.setObjectName(ObjectNames.TEXT_SECONDARY)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)

        layout.addSpacing(4)

        # Input Form Area
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(Spacing.XS)

        lbl_pass_label = QLabel("MASTER PASSWORD")
        lbl_pass_label.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 9.5px; font-weight: 800; letter-spacing: 0.8px; font-family: monospace;"
        )
        input_layout.addWidget(lbl_pass_label)

        self.lbl_caps = QLabel("Caps Lock is ON")
        self.lbl_caps.setStyleSheet(f"color: {Colors.STATUS_OVERDUE}; font-size: 10.5px; font-weight: 600;")
        self.lbl_caps.setVisible(False)

        self.txt_password = _PasswordLineEdit(self.lbl_caps)
        self.txt_password.setObjectName(ObjectNames.GP_SUPER_INPUT)
        self.txt_password.setPlaceholderText("Enter Admin Password...")
        self.txt_password.addAction(
            IconHelper.get_icon("shield", color=Colors.ACCENT_GOLD, size=16),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.txt_password.returnPressed.connect(self._handle_login)
        input_layout.addWidget(self.txt_password)

        input_layout.addWidget(self.lbl_caps)
        layout.addWidget(input_container)

        # Error Display
        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName(ObjectNames.FORM_ERROR_LABEL)
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setWordWrap(True)
        layout.addWidget(self.lbl_error)

        layout.addSpacing(4)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(Spacing.MD)

        self.btn_login = QPushButton("Authenticate")
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setObjectName(ObjectNames.BTN_PRIMARY)
        self.btn_login.setIcon(IconHelper.get_icon("shield-check", color=Colors.BACKGROUND, size=16))
        self.btn_login.clicked.connect(self._handle_login)
        attach_press_feedback(self.btn_login)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setObjectName(ObjectNames.BTN_CANCEL)
        btn_cancel.clicked.connect(self.reject)
        attach_press_feedback(btn_cancel)

        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.txt_password.setFocus()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fade_anim = fade_in_widget(self)

    def _shake_dialog(self) -> None:
        """Visual shake animation indicating authentication failure."""
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

    def _handle_login(self) -> None:
        password = self.txt_password.text().strip()

        if not password:
            self.lbl_error.setText("Please enter the administrator password.")
            self._shake_dialog()
            return

        self.btn_login.setEnabled(False)
        try:
            admin = self.auth_service.authenticate(password)
            self.authenticated_admin = admin
            self.accept()
        except AuthenticationError as e:
            self.lbl_error.setText(str(e))
            self.txt_password.clear()
            self.txt_password.setFocus()
            self._shake_dialog()
        except Exception:
            logger.exception("Unexpected error during admin authentication")
            self.lbl_error.setText("An unexpected error occurred. Please try again.")
            self.txt_password.clear()
            self.txt_password.setFocus()
            self._shake_dialog()
        finally:
            self.btn_login.setEnabled(True)


AdminLoginDialog = AdminAuthDialog