""""Top-level Kiosk Main Window supporting window controls and title bar layout."""

import sys
from pathlib import Path
from datetime import datetime

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
from src.ui.theme import Colors, ObjectNames
from src.ui.views.admin_dashboard.dashboard_main import AdminDashboardWindow
from src.ui.views.admin_login import AdminAuthDialog
from src.ui.views.shutdown_dialog import ShutdownAuthDialog
from src.ui.views.station_view import StationView
from src.utils.icon_helper import IconHelper
from src.utils.time_utils import PHT_TIMEZONE


class MainWindow(QMainWindow):
    """Main window embedding the attendance station kiosk and administration controls."""

    def __init__(self, db_manager: DatabaseConnectionManager, parent=None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.dashboard = None

        # Simplified per this session's UX pass: the old "(Desktop Terminal
        # v2.4)" suffix was a dev-build artifact duplicated on-screen; the
        # window title itself is rarely user-visible on a kiosk anyway.
        self.setWindowTitle("The Gold Panicles — Attendance System")
        self.setMinimumSize(1024, 640)

        if getattr(sys, "frozen", False):
            self._base_dir = Path(sys._MEIPASS)
        else:
            self._base_dir = Path(__file__).resolve().parent.parent.parent

        self._logo_path = self._base_dir / "assets" / "images" / "logo.png"
        if self._logo_path.exists():
            self.setWindowIcon(QIcon(str(self._logo_path)))

        self._init_ui()

        self.f2_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F2), self)
        self.f2_shortcut.activated.connect(self._trigger_manual_entry)

        # NEW THIS SESSION: F11 toggles distraction-free fullscreen kiosk
        # mode. There is intentionally no on-screen "exit fullscreen"
        # button -- pressing F11 again, the window manager's close control,
        # or Alt+F4 all still route through closeEvent()'s
        # ShutdownAuthDialog guard exactly as before. Removing the in-app
        # Exit button does NOT remove the admin-authorization requirement
        # to actually quit the application.
        self.f11_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        self.f11_shortcut.activated.connect(self._toggle_fullscreen)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _init_ui(self) -> None:
        central_container = QWidget()
        main_layout = QVBoxLayout(central_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # REMOVED THIS SESSION: the old 32px "Desktop OS Header Bar" that
        # duplicated the window title text ("The Gold Panicles — Attendance
        # System (Desktop Terminal v2.4)") as a second, redundant on-screen
        # label above the real brand header. The brand header below already
        # carries full brand identity.

        # Brand Title Bar & Header Actions
        header = QFrame()
        header.setFixedHeight(54)
        header.setObjectName(ObjectNames.MAIN_HEADER_FRAME)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)
        header_layout.setSpacing(12)

        if self._logo_path.exists():
            lbl_logo = QLabel()
            pix = QPixmap(str(self._logo_path)).scaled(
                32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pix)
            header_layout.addWidget(lbl_logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)

        lbl_title = QLabel("THE GOLD PANICLES")
        lbl_title.setObjectName(ObjectNames.BRAND_TITLE)

        lbl_subtitle = QLabel("Official Student Publication of Caraga State University — Main Campus")
        lbl_subtitle.setObjectName(ObjectNames.TEXT_SECONDARY)

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_subtitle)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        self.lbl_clock = QLabel("")
        self.lbl_clock.setObjectName(ObjectNames.LIVE_CLOCK)
        header_layout.addWidget(self.lbl_clock)

        btn_admin = QPushButton("Admin Console")
        btn_admin.setObjectName(ObjectNames.BTN_CHROME)
        btn_admin.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_admin.setIcon(IconHelper.get_icon("shield", color=Colors.TEXT_PRIMARY, size=16))
        btn_admin.setIconSize(QSize(16, 16))
        btn_admin.clicked.connect(self._open_admin_console)
        attach_press_feedback(btn_admin)
        header_layout.addWidget(btn_admin)

        # REMOVED THIS SESSION: the header "Exit" button. Quitting is still
        # fully gated behind ShutdownAuthDialog via closeEvent() below --
        # reachable via the window manager's close control or Alt+F4 -- this
        # only removes the redundant always-visible in-app button.

        main_layout.addWidget(header)

        # Workstation Area
        self.station_view = StationView(self.db_manager, parent=self)
        main_layout.addWidget(self.station_view, stretch=1)

        self.setCentralWidget(central_container)

    def _trigger_manual_entry(self) -> None:
        if hasattr(self, "station_view") and hasattr(self.station_view, "focus_hardware_input"):
            self.station_view.focus_hardware_input()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
        QTimer.singleShot(0, self._trigger_manual_entry)

    def _update_clock(self) -> None:
        pht_now = datetime.now(PHT_TIMEZONE)
        self.lbl_clock.setText(pht_now.strftime("%b %d, %Y  •  %I:%M:%S %p PHT"))

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