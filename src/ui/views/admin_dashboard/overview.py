"""
Overview Tab: at-a-glance dashboard metrics cards for the Admin Dashboard.
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.visitor_repo import VisitorRepository
from src.ui.theme import Colors, ObjectNames, Radius, Spacing
from src.utils.icon_helper import IconHelper

logger = logging.getLogger(__name__)


class StatCard(QFrame):
    """Themed dashboard summary metric card with visual icon accents."""

    def __init__(
        self,
        title: str,
        value: str = "0",
        icon_name: str = "layers",
        accent_color: str = Colors.ACCENT_GOLD,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName(ObjectNames.STAT_CARD)
        self.setStyleSheet(
            f"""
            QFrame#{ObjectNames.STAT_CARD} {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.BORDER};
                border-radius: {Radius.CARD}px;
                border-left: 4px solid {accent_color};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        layout.setSpacing(Spacing.XS)

        title_row = QHBoxLayout()
        title_row.setSpacing(Spacing.XS)

        self.lbl_icon = QLabel()
        self.lbl_icon.setPixmap(IconHelper.get_pixmap(icon_name, color=Colors.TEXT_MUTED, size=14))
        self.lbl_icon.setStyleSheet("background: transparent;")
        title_row.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setObjectName(ObjectNames.STAT_CARD_TITLE)
        self.lbl_title.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; font-weight: 800; letter-spacing: 0.8px; font-family: monospace; background: transparent;"
        )
        title_row.addWidget(self.lbl_title)
        title_row.addStretch()

        layout.addLayout(title_row)

        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName(ObjectNames.STAT_CARD_VALUE)
        self.lbl_value.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 26px; font-weight: 800; font-family: monospace; background: transparent;"
        )
        layout.addWidget(self.lbl_value)
        layout.addStretch()


class OverviewView(QWidget):
    """Main overview metrics view tab inside the admin dashboard."""

    def __init__(self, attendance_repo_or_db, parent=None):
        super().__init__(parent)

        self._visitor_repo: Optional[VisitorRepository] = None
        if isinstance(attendance_repo_or_db, AttendanceRepository):
            self.repo = attendance_repo_or_db
        else:
            self.repo = AttendanceRepository(attendance_repo_or_db)
            try:
                self._visitor_repo = VisitorRepository(attendance_repo_or_db)
            except Exception:
                logger.warning(
                    "OverviewView: could not construct VisitorRepository for overdue-flag refresh.",
                    exc_info=True,
                )

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        main_layout.setSpacing(Spacing.MD)

        # Section Title Row
        header_row = QHBoxLayout()
        header_row.setSpacing(Spacing.XS)

        icon_title = QLabel()
        icon_title.setPixmap(IconHelper.get_pixmap("activity", color=Colors.ACCENT_GOLD, size=18))
        icon_title.setStyleSheet("background: transparent;")
        header_row.addWidget(icon_title)

        header_label = QLabel("SYSTEM OVERVIEW & LIVE METRICS")
        header_label.setObjectName(ObjectNames.SECTION_TITLE)
        header_label.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 14px; font-weight: 800; letter-spacing: 0.8px;"
        )
        header_row.addWidget(header_label)
        header_row.addStretch()

        main_layout.addLayout(header_row)

        # Metrics Card Grid
        grid = QGridLayout()
        grid.setSpacing(Spacing.MD)

        self.card_in_office = StatCard("Staff In Office", "0", icon_name="briefcase", accent_color=Colors.STATUS_COMPLETED)
        self.card_visitors = StatCard("Active Visitors", "0", icon_name="users", accent_color=Colors.STATUS_OPEN)
        self.card_overdue = StatCard("Overdue Sessions", "0", icon_name="alert-triangle", accent_color=Colors.DANGER_SOLID)
        self.card_total_today = StatCard("Total Entries Today", "0", icon_name="layers", accent_color=Colors.ACCENT_GOLD)

        grid.addWidget(self.card_in_office, 0, 0)
        grid.addWidget(self.card_visitors, 0, 1)
        grid.addWidget(self.card_overdue, 1, 0)
        grid.addWidget(self.card_total_today, 1, 1)

        main_layout.addLayout(grid)
        main_layout.addStretch()

        self.refresh_metrics()

    def refresh_metrics(self) -> None:
        """Sweeps overdue sessions and refreshes stat card metrics."""
        try:
            self.repo.flag_overdue_sessions()
            if self._visitor_repo is not None:
                self._visitor_repo.flag_overdue_visits()

            metrics = self.repo.get_dashboard_metrics()
        except Exception:
            logger.exception("Failed to load dashboard overview metrics.")
            return

        self.card_in_office.lbl_value.setText(str(metrics.get("staff_in_office", 0)))
        self.card_visitors.lbl_value.setText(str(metrics.get("active_visitors", 0)))
        self.card_overdue.lbl_value.setText(str(metrics.get("overdue_sessions", 0)))
        self.card_total_today.lbl_value.setText(str(metrics.get("total_entries_today", 0)))


OverviewTab = OverviewView