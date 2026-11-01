""""Top-level Kiosk Main Window supporting window controls, title bar layout, and workstation routing."""

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.database.connection import DatabaseConnectionManager
from src.ui.components.animations import attach_press_feedback
from src.ui.theme import Colors, ObjectNames, Radius, Spacing, Typography
from src.ui.views.admin_dashboard.dashboard_main import AdminDashboardWindow
from src.ui.views.admin_login import AdminAuthDialog
from src.ui.views.shutdown_dialog import ShutdownAuthDialog
from src.ui.views.station_view import StationView
from src.utils.icon_helper import IconHelper
from src.utils.time_utils import PHT_TIMEZONE


class MainWindow(QMainWindow):
    """Main workstation shell embedding the attendance station kiosk and administrative controls."""

    def __init__(self, db_manager: DatabaseConnectionManager, parent=None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.dashboard = None

        self.setWindowTitle("The Gold Panicles")
        self.setMinimumSize(1280, 768)

        if getattr(sys, "frozen", False):
            self._base_dir = Path(sys._MEIPASS)
        else:
            self._base_dir = Path(__file__).resolve().parent.parent.parent

        self._logo_path = self._base_dir / "assets" / "images" / "logo.png"
        if self._logo_path.exists():
            self.setWindowIcon(QIcon(str(self._logo_path)))

        self._init_ui()
        self._register_keyboard_shortcuts()

        # Real-time PHT Clock Timer
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _register_keyboard_shortcuts(self) -> None:
        """Configures global workstation keyboard navigation shortcuts."""
        # F2: Focus Primary Hardware Input Receiver
        self.f2_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F2), self)
        self.f2_shortcut.activated.connect(self._trigger_manual_entry)

        # F5: Refresh Attendance Board Feed
        self.f5_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F5), self)
        self.f5_shortcut.activated.connect(self._trigger_refresh)

        # F11: Toggle Fullscreen Mode
        self.f11_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        self.f11_shortcut.activated.connect(self._toggle_fullscreen)

        # Escape: Clear Input and Restore Receiver Focus
        self.esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.esc_shortcut.activated.connect(self._handle_escape)

    def _init_ui(self) -> None:
        central_container = QWidget()
        central_container.setObjectName("mainContainer")

        main_layout = QVBoxLayout(central_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Masthead Header Bar (64px standard height)
        header = QFrame()
        header.setFixedHeight(64)
        header.setObjectName(ObjectNames.MAIN_HEADER_FRAME)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(Spacing.MD, 0, Spacing.MD, 0)
        header_layout.setSpacing(Spacing.MD)

        if self._logo_path.exists():
            lbl_logo = QLabel()
            pix = QPixmap(str(self._logo_path)).scaled(
                34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pix)
            lbl_logo.setStyleSheet("background: transparent; border: none;")
            header_layout.addWidget(lbl_logo, alignment=Qt.AlignmentFlag.AlignVCenter)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_box.setContentsMargins(0, 8, 0, 8)

        lbl_title = QLabel("THE GOLD PANICLES")
        lbl_title.setObjectName(ObjectNames.BRAND_TITLE)

        lbl_subtitle = QLabel("Official Student Publication of Caraga State University — Main Campus")
        lbl_subtitle.setObjectName(ObjectNames.TEXT_SECONDARY)

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Live Clock Display
        self.lbl_clock = QLabel("")
        self.lbl_clock.setObjectName(ObjectNames.LIVE_CLOCK)
        self.lbl_clock.setFixedHeight(36)
        self.lbl_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.lbl_clock, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Admin Auth Trigger
        btn_admin = QPushButton(" Admin Console")
        btn_admin.setObjectName(ObjectNames.BTN_CHROME)
        btn_admin.setFixedHeight(36)
        btn_admin.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_admin.setIcon(IconHelper.get_icon("shield", color=Colors.ACCENT_GOLD, size=15))
        btn_admin.setIconSize(QSize(15, 15))
        btn_admin.clicked.connect(self._open_admin_console)
        attach_press_feedback(btn_admin)
        header_layout.addWidget(btn_admin, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addWidget(header)

        # Primary Kiosk Workstation Viewport
        self.station_view = StationView(self.db_manager, parent=self)
        main_layout.addWidget(self.station_view, stretch=1)

        self.setCentralWidget(central_container)

    def _trigger_manual_entry(self) -> None:
        if hasattr(self, "station_view") and hasattr(self.station_view, "focus_hardware_input"):
            self.station_view.focus_hardware_input()

    def _trigger_refresh(self) -> None:
        if hasattr(self, "station_view"):
            if hasattr(self.station_view, "force_refresh"):
                self.station_view.force_refresh()
            elif hasattr(self.station_view, "refresh_board"):
                self.station_view.refresh_board()

    def _handle_escape(self) -> None:
        if hasattr(self, "station_view"):
            if hasattr(self.station_view, "hardware_input"):
                self.station_view.hardware_input.clear()
            if hasattr(self.station_view, "focus_hardware_input"):
                self.station_view.focus_hardware_input()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        QTimer.singleShot(50, self._trigger_manual_entry)

    def _update_clock(self) -> None:
        pht_now = datetime.now(PHT_TIMEZONE)
        self.lbl_clock.setText(pht_now.strftime("%b %d, %Y  •  %I:%M:%S %p PHT").upper())

    def _open_admin_console(self) -> None:
        if self.dashboard is not None:
            try:
                self.dashboard.close()
            except RuntimeError:
                pass
            self.dashboard.deleteLater()
            self.dashboard = None

        auth_dialog = AdminAuthDialog(self.db_manager, parent=self)
        if auth_dialog.exec() == AdminAuthDialog.DialogCode.Accepted and auth_dialog.authenticated_admin:
            self.dashboard = AdminDashboardWindow(
                db_manager=self.db_manager,
                admin_user=auth_dialog.authenticated_admin,
            )
            self.dashboard.show()

        if hasattr(self, "station_view"):
            self.station_view.refresh_board()
            self.station_view.focus_hardware_input()

    def closeEvent(self, event) -> None:
        dialog = ShutdownAuthDialog(self.db_manager, parent=self)
        if dialog.exec() == ShutdownAuthDialog.DialogCode.Accepted and dialog.authorized:
            if self.dashboard is not None:
                try:
                    self.dashboard.close()
                except RuntimeError:
                    pass
                self.dashboard.deleteLater()
                self.dashboard = None
            event.accept()
        else:
            event.ignore()