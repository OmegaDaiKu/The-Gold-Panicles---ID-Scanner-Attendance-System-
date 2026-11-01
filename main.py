""""Application entry point for The Gold Panicles QR Attendance System."""

import logging
import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer
from src.services.auth_service import AuthService
from src.ui.main_window import MainWindow
from src.ui.theme import STYLESHEET_RELATIVE_PATH
from src.utils.font_loader import load_application_fonts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AttendanceApplication:
    """Application runner initializing database, default admin credentials, and main window."""

    def __init__(self):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        self.app = QApplication(sys.argv)
        self.app.setStyle("Fusion")

        if hasattr(sys, "_MEIPASS"):
            base_dir = Path(sys._MEIPASS)
        else:
            base_dir = Path(__file__).resolve().parent

        loaded_fonts = load_application_fonts(base_dir)
        unique_families = sorted(set(loaded_fonts)) if loaded_fonts else []
        if unique_families:
            logger.info("Custom fonts available this session: %s", ", ".join(unique_families))

        # Font configuration
        if "M Ying Hei PRC W5" in unique_families:
            self.app.setFont(QFont("M Ying Hei PRC W5", 10))
        elif "M Ying Hei PRC" in unique_families:
            self.app.setFont(QFont("M Ying Hei PRC", 10))
        elif "Helvetica Neue" in unique_families:
            self.app.setFont(QFont("Helvetica Neue", 10))
        elif "Helvetica" in unique_families:
            self.app.setFont(QFont("Helvetica", 10))
        else:
            app_font = QFont("M Ying Hei PRC W5", 10)
            app_font.setStyleHint(QFont.StyleHint.SansSerif)
            self.app.setFont(app_font)

        qss_path = base_dir / STYLESHEET_RELATIVE_PATH
        if qss_path.exists():
            with open(qss_path, "r", encoding="utf-8") as f:
                self.app.setStyleSheet(f.read())

        icon_path = base_dir / "assets" / "images" / "logo.png"
        if icon_path.exists():
            self.app.setWindowIcon(QIcon(str(icon_path)))

        self.db_manager = DatabaseConnectionManager()
        self.schema_init = SchemaInitializer(self.db_manager)
        self.schema_init.ensure_schema_exists()

        self.auth_service = AuthService(self.db_manager)
        self.auth_service.ensure_default_admin_exists()

        self.main_window = MainWindow(self.db_manager)
        self.main_window.showMaximized()

    def run(self) -> int:
        return self.app.exec()


if __name__ == "__main__":
    app_runner = AttendanceApplication()
    sys.exit(app_runner.run())