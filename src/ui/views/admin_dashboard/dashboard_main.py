"""""Top-Level QMainWindow Admin Dashboard container hosting the management tabs."""

import logging
import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.database.connection import DatabaseConnectionManager
from src.ui.theme import ObjectNames
from src.ui.views.admin_dashboard.overview import OverviewTab
from src.ui.views.admin_dashboard.staff_mgmt import StaffManagementTab
from src.ui.views.admin_dashboard.attendance_logs import AttendanceLogsTab
from src.ui.views.admin_dashboard.overdue_resolution import OverdueResolutionTab
from src.ui.views.admin_dashboard.reports import ReportsExportsTab
from src.ui.views.admin_dashboard.settings_view import SettingsViewTab
from src.utils.time_utils import PHT_TIMEZONE

logger = logging.getLogger(__name__)


def _get_base_dir() -> Path:
    """FIXED THIS SESSION: previously this file resolved its base directory
    inline as `Path(__file__).parent.parent.parent.parent` -- but this file
    lives at src/ui/views/admin_dashboard/dashboard_main.py, ONE directory
    deeper than admin_login.py (src/ui/views/admin_login.py), which uses
    that same 4-parent pattern correctly for its own, shallower location.
    Four parents from here lands on src/, not the project root, so
    self._logo_path.exists() was always False: the window icon silently
    never got set, and the header's logo block silently never ran. Also
    added frozen/_MEIPASS handling to match admin_login.py's existing
    _get_base_dir(), since this file previously had none at all -- it
    would have resolved incorrectly in a packaged build on top of the
    directory-depth bug.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).parent.parent.parent.parent.parent


class AdminDashboardWindow(QMainWindow):
    """Standalone Top-Level Admin Dashboard Window."""

    def __init__(self, db_manager: DatabaseConnectionManager, admin_user: dict, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.admin_user = admin_user

        if not self.admin_user or self.admin_user.get("id") is None:
            raise ValueError(
                "AdminDashboardWindow requires an authenticated admin_user dict "
                "containing a valid 'id'. Received: {!r}".format(self.admin_user)
            )
        self.admin_id = self.admin_user["id"]

        self.setWindowTitle("The Gold Panicles – Administrator Dashboard")
        self.resize(1200, 780)
        self.setMinimumSize(1000, 640)

        self._logo_path = _get_base_dir() / "assets" / "images" / "logo.png"
        if self._logo_path.exists():
            self.setWindowIcon(QIcon(str(self._logo_path)))

        self._init_ui()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    def _init_ui(self) -> None:
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Branding Bar
        header = QWidget()
        header.setObjectName(ObjectNames.MAIN_HEADER_FRAME)
        header.setFixedHeight(64)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(14)

        if self._logo_path.exists():
            lbl_logo = QLabel()
            pixmap = QPixmap(str(self._logo_path)).scaled(
                38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            lbl_logo.setPixmap(pixmap)
            lbl_logo.setStyleSheet("background: transparent;")
            header_layout.addWidget(lbl_logo, alignment=Qt.AlignmentFlag.AlignVCenter)

        brand_vbox = QVBoxLayout()
        brand_vbox.setSpacing(0)
        brand_vbox.setContentsMargins(0, 0, 0, 0)

        lbl_brand = QLabel("THE GOLD PANICLES")
        lbl_brand.setObjectName(ObjectNames.BRAND_TITLE)

        lbl_sub = QLabel("Administrator Dashboard • Editorial Year 2026–2027")
        lbl_sub.setObjectName(ObjectNames.TEXT_SECONDARY)

        brand_vbox.addWidget(lbl_brand)
        brand_vbox.addWidget(lbl_sub)
        header_layout.addLayout(brand_vbox)
        header_layout.setAlignment(brand_vbox, Qt.AlignmentFlag.AlignVCenter)

        header_layout.addStretch()

        self.lbl_clock = QLabel("")
        self.lbl_clock.setObjectName(ObjectNames.LIVE_CLOCK)
        self.lbl_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_clock.setFixedHeight(30)
        self.lbl_clock.setMinimumWidth(195)
        header_layout.addWidget(self.lbl_clock, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_layout.addSpacing(10)

        admin_name = self.admin_user.get("username", "admin").upper()
        lbl_admin_badge = QLabel(f"  ● {admin_name}  ")
        lbl_admin_badge.setObjectName(ObjectNames.ADMIN_USER_BADGE)
        header_layout.addWidget(lbl_admin_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_layout.addSpacing(8)

        btn_close = QPushButton("← Return to Kiosk")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setObjectName(ObjectNames.BTN_CHROME)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addWidget(header)

        # Tab Navigation Container
        self.tabs = QTabWidget()
        admin_id = self.admin_id

        self.tab_overview = OverviewTab(self.db_manager)
        self.tab_staff = StaffManagementTab(self.db_manager, admin_id=admin_id)
        self.tab_logs = AttendanceLogsTab(self.db_manager, admin_id=admin_id)
        self.tab_overdue = OverdueResolutionTab(self.db_manager, admin_id=admin_id)
        self.tab_reports = ReportsExportsTab(self.db_manager, admin_id=admin_id)
        self.tab_settings = SettingsViewTab(self.db_manager, admin_id=admin_id)

        self.tabs.addTab(self.tab_overview, "Overview")
        self.tabs.addTab(self.tab_staff, "Staff Directory")
        self.tabs.addTab(self.tab_logs, "Attendance Logs")
        self.tabs.addTab(self.tab_overdue, "Overdue Resolution")
        self.tabs.addTab(self.tab_reports, "Reports & Exports")
        self.tabs.addTab(self.tab_settings, "Settings & Backups")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tabs)
        self.setCentralWidget(central_widget)

    def _update_clock(self) -> None:
        pht_now = datetime.now(PHT_TIMEZONE)
        self.lbl_clock.setText(pht_now.strftime("%b %d, %Y  •  %I:%M:%S %p PHT"))

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        try:
            if widget is self.tab_overview and hasattr(widget, 'refresh_metrics'):
                widget.refresh_metrics()
            elif widget is self.tab_staff and hasattr(widget, 'refresh_table'):
                widget.refresh_table()
            elif widget is self.tab_logs and hasattr(widget, 'refresh_logs'):
                widget.refresh_logs()
            elif widget is self.tab_overdue and hasattr(widget, 'refresh_table'):
                widget.refresh_table()
            elif widget is self.tab_settings and hasattr(widget, 'refresh_backups_list'):
                widget.refresh_backups_list()
        except Exception:
            logger.exception(
                "Failed to refresh admin dashboard tab at index %s (%s)",
                index,
                type(widget).__name__ if widget is not None else "None",
            )

    def closeEvent(self, event) -> None:
        if hasattr(self, "clock_timer") and self.clock_timer is not None:
            self.clock_timer.stop()
        super().closeEvent(event)