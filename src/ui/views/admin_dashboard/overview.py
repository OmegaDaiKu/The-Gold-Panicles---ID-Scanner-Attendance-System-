""""Overview Tab: at-a-glance dashboard metrics cards for the Admin Dashboard."""

import logging

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QGridLayout
from PySide6.QtCore import Qt
from src.database.repositories.attendance_repo import AttendanceRepository
from src.database.repositories.visitor_repo import VisitorRepository
from src.ui.theme import ObjectNames

logger = logging.getLogger(__name__)


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setObjectName(ObjectNames.STAT_CARD)
        layout = QVBoxLayout(self)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName(ObjectNames.STAT_CARD_TITLE)

        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName(ObjectNames.STAT_CARD_VALUE)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addStretch()


class OverviewView(QWidget):
    def __init__(self, attendance_repo_or_db, parent=None):
        super().__init__(parent)

        # FIXED THIS SESSION: refresh_metrics() previously read
        # attendance_sessions/visitor_visits status counts directly with no
        # overdue-flagging sweep beforehand, unlike every other consumer of
        # overdue state in the app (AttendanceService._refresh_overdue_flags(),
        # OverdueService.get_overdue_records()). In practice the sweep runs
        # constantly as a side effect of scan activity, but a dashboard opened
        # before the first scan of the day (e.g. first thing in the morning)
        # could show sessions that crossed the overnight midnight-boundary
        # into OVERDUE still counted under "Staff In Office". We now flag
        # overdue sessions/visits directly via the repos below immediately
        # before reading metrics, matching the minimal no-service-layer
        # pattern this file already uses (same pattern as reports.py).
        #
        # self._visitor_repo is only constructible when we were handed a raw
        # db_manager (the only way dashboard_main.py actually calls this
        # constructor today: `OverviewTab(self.db_manager)`). If this view
        # is ever constructed with an already-built AttendanceRepository
        # instance instead (a code path that exists but is not currently
        # used anywhere seen this session), there is no way to recover a
        # db_manager handle to build a VisitorRepository from it, so visitor
        # overdue-flagging is skipped gracefully in that case rather than
        # failing -- attendance-session flagging still runs either way.
        self._visitor_repo = None
        if isinstance(attendance_repo_or_db, AttendanceRepository):
            self.repo = attendance_repo_or_db
        else:
            self.repo = AttendanceRepository(attendance_repo_or_db)
            try:
                self._visitor_repo = VisitorRepository(attendance_repo_or_db)
            except Exception:
                logger.warning(
                    "OverviewView: could not construct VisitorRepository for "
                    "overdue-flag refresh; visitor OVERDUE status may be "
                    "stale on this tab until the next scan or board refresh.",
                    exc_info=True,
                )

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        header_label = QLabel("SYSTEM OVERVIEW")
        header_label.setObjectName(ObjectNames.SECTION_TITLE)
        main_layout.addWidget(header_label)

        grid = QGridLayout()
        grid.setSpacing(16)

        self.card_in_office = StatCard("Staff In Office")
        self.card_visitors = StatCard("Active Visitors")
        self.card_overdue = StatCard("Overdue Sessions")
        self.card_total_today = StatCard("Total Entries Today")

        grid.addWidget(self.card_in_office, 0, 0)
        grid.addWidget(self.card_visitors, 0, 1)
        grid.addWidget(self.card_overdue, 1, 0)
        grid.addWidget(self.card_total_today, 1, 1)

        main_layout.addLayout(grid)
        main_layout.addStretch()

        self.refresh_metrics()

    def refresh_metrics(self):
        try:
            # Sweep overdue status BEFORE reading counts -- see __init__ note.
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