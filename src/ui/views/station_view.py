"""Main Kiosk Station View — Parity build matching HTML v2.4 layout matrix."""

import csv
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QDate, QEasingCurve, QEvent, QPropertyAnimation, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.database.connection import DatabaseConnectionManager
from src.services.attendance_service import AttendanceService
from src.ui.components.animations import attach_press_feedback
from src.ui.components.attendance_board import AttendanceBoardWidget
from src.ui.components.modals import GuestVisitorNameDialog
from src.ui.components.toast import show_toast
from src.ui.theme import Colors, ObjectNames, Spacing
from src.ui.widgets.gold_calendar import GoldCalendar
from src.ui.widgets.pill_widget import PillWidget
from src.utils.icon_helper import IconHelper
from src.utils.time_utils import PHT_TIMEZONE

logger = logging.getLogger(__name__)

QR_SCAN_DEBOUNCE_SECONDS = 2.0
BOARD_AUTO_REFRESH_MS = 30_000
FOCUS_GUARD_INTERVAL_MS = 250
EDGE_GLOW_DURATION_MS = 300

STATUS_FILTERS = [
    ("All", "ALL", "list"),
    ("Active Duty", "OPEN", "user-check"),
    ("Overdue", "OVERDUE", "alert-triangle"),
    ("Completed", "COMPLETED", "check-circle"),
]

_VERIFY_ICON_DEFAULT = "scan-line"
_FOCUS_GUARD_RELEASE_DELAY_MS = 150


class StationView(QWidget):
    """Main front-desk attendance station view with 2-panel architecture."""

    def __init__(self, db_manager: DatabaseConnectionManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.attendance_service = AttendanceService(db_manager)

        self._viewing_date = None
        self._modal_active = False
        self._dates_with_records: Optional[set] = None

        self._last_full_feed: list = []
        self._current_status_filter: str = "ALL"

        self._last_scanned_payload = None
        self._last_scan_timestamp = None
        self._active_toast = None

        # Guards against the hardware-input refocus timer stealing focus
        # away from a button mid-click (see _install_focus_guard_exemptions).
        self._focus_guard_suspended = False
        self._focus_guard_exempt_widgets: set = set()

        self._init_ui()
        self.refresh_board()

        self._board_refresh_timer = QTimer(self)
        self._board_refresh_timer.timeout.connect(self.refresh_board)
        self._board_refresh_timer.start(BOARD_AUTO_REFRESH_MS)

        self._focus_guard_timer = QTimer(self)
        self._focus_guard_timer.timeout.connect(self._enforce_hardware_input_focus)
        self._focus_guard_timer.start(FOCUS_GUARD_INTERVAL_MS)

        self.focus_hardware_input()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.MD)

        # 70% Left Section (Column 8) / 30% Right Sidebar (Column 4)
        layout.addWidget(self._build_main_column(), 70)
        layout.addWidget(self._build_sidebar(), 30)

        # Scan Flash Edge Feedback Overlay
        self._edge_glow_overlay = QFrame(self)
        self._edge_glow_overlay.setObjectName("edgeGlowOverlay")
        self._edge_glow_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._edge_glow_overlay.setStyleSheet(
            "QFrame#edgeGlowOverlay { background-color: transparent; border: none; }"
        )
        self._edge_glow_effect = QGraphicsOpacityEffect(self._edge_glow_overlay)
        self._edge_glow_effect.setOpacity(0.0)
        self._edge_glow_overlay.setGraphicsEffect(self._edge_glow_effect)
        self._edge_glow_anim = QPropertyAnimation(self._edge_glow_effect, b"opacity", self)
        self._edge_glow_overlay.setGeometry(self.rect())
        self._edge_glow_overlay.show()
        self._edge_glow_overlay.raise_()

        # Must run last, after every button in the view tree exists.
        self._install_focus_guard_exemptions()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_edge_glow_overlay"):
            self._edge_glow_overlay.setGeometry(self.rect())

    def _make_super_card(
        self,
        title: Optional[str] = None,
        decorative: bool = False,
        accent_color: Optional[str] = None,
    ) -> QFrame:
        card = QFrame()
        if decorative:
            # The asymmetric "Super Graphic" brand treatment is intentionally
            # reserved for low-density, mostly-idle surfaces (the calendar,
            # the last-scan-result panel) instead of every card -- on dense
            #/functional surfaces (the table, the input row, the metric
            # tiles) it competed with real content rather than enhancing it.
            card.setObjectName(ObjectNames.CARD_SUPER)
        else:
            border_left = f"border-left: 3px solid {accent_color};" if accent_color else ""
            card.setStyleSheet(
                "QFrame { background-color: #101014; border: 1px solid #202024; "
                f"border-radius: 10px; {border_left} }}"
            )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.XS)
        if title:
            lbl = QLabel(title.upper())
            lbl.setStyleSheet(
                "color: #F4EFEA; font-weight: 800; font-size: 10px; "
                "letter-spacing: 0.5px; background: transparent;"
            )
            layout.addWidget(lbl)
        return card

    @staticmethod
    def _icon_button_style() -> str:
        return (
            "QPushButton { background-color: #1C1C20; border: 1px solid #24242A; "
            "border-radius: 6px; padding: 0px; } "
            "QPushButton:hover { border-color: #DAA520; background-color: #24242A; }"
            "QPushButton:disabled { border-color: #1C1C20; }"
        )

    @staticmethod
    def _eyebrow_label(text: str, icon_name: Optional[str] = None) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        if icon_name:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(IconHelper.get_pixmap(icon_name, color="#8E8E93", size=11))
            icon_lbl.setStyleSheet("background: transparent;")
            row.addWidget(icon_lbl)
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            "color: #8E8E93; font-weight: 800; font-size: 9px; "
            "letter-spacing: 1px; background: transparent;"
        )
        row.addWidget(lbl)
        row.addStretch()
        return wrap

    # ------------------------------------------------------------------
    # Focus-guard hover/click exemption
    # ------------------------------------------------------------------

    def _install_focus_guard_exemptions(self) -> None:
        """Prevent the periodic hardware-input refocus guard from stealing
        focus away from a button while the user is hovering/clicking it.

        Root cause of the 'need to double-click buttons' bug: the guard
        timer fires every FOCUS_GUARD_INTERVAL_MS regardless of what the
        user is doing, and could reclaim focus mid-click, cancelling the
        press/release sequence on whatever button was being pressed.
        """
        for btn in self.findChildren(QPushButton):
            btn.installEventFilter(self)
            self._focus_guard_exempt_widgets.add(btn)

    def eventFilter(self, obj, event) -> bool:
        if obj in self._focus_guard_exempt_widgets:
            et = event.type()
            if et in (QEvent.Type.Enter, QEvent.Type.MouseButtonPress):
                self._focus_guard_suspended = True
            elif et in (QEvent.Type.Leave, QEvent.Type.MouseButtonRelease):
                QTimer.singleShot(_FOCUS_GUARD_RELEASE_DELAY_MS, self._maybe_release_focus_guard)
        return super().eventFilter(obj, event)

    def _maybe_release_focus_guard(self) -> None:
        widget_under_cursor = QApplication.widgetAt(QCursor.pos())
        if widget_under_cursor not in self._focus_guard_exempt_widgets:
            self._focus_guard_suspended = False

    # ------------------------------------------------------------------
    # Left Main Section (Log Stream & Receiver)
    # ------------------------------------------------------------------

    def _build_main_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        # Hardware Scanner Receiver Bar
        layout.addWidget(self._build_receiver_card())

        # Log Table Container
        table_container = self._make_super_card(None)
        table_layout = table_container.layout()

        table_layout.addWidget(self._eyebrow_label("Attendance Log", icon_name="list"))

        # Toolbar & Filters Row
        table_layout.addWidget(self._build_search_filter_row())

        # Attendance Table
        self.board_widget = AttendanceBoardWidget()
        table_layout.addWidget(self.board_widget, stretch=1)

        # Table Footer Summary
        footer_row = QHBoxLayout()

        self.lbl_record_count = QLabel("Showing: 0 entries")
        self.lbl_record_count.setStyleSheet("color: #8E8E93; font-family: monospace; font-size: 10px;")
        footer_row.addWidget(self.lbl_record_count)
        footer_row.addSpacing(12)

        sync_box = QHBoxLayout()
        sync_box.setSpacing(4)
        sync_icon = QLabel()
        sync_icon.setPixmap(IconHelper.get_pixmap("database", color="#34D399", size=10))
        sync_icon.setStyleSheet("background: transparent;")
        sync_box.addWidget(sync_icon)
        lbl_sync = QLabel("Database Synced")
        lbl_sync.setStyleSheet("color: #34D399; font-family: monospace; font-size: 10px;")
        sync_box.addWidget(lbl_sync)
        footer_row.addLayout(sync_box)

        footer_row.addStretch()

        table_layout.addLayout(footer_row)

        layout.addWidget(table_container, stretch=1)
        return col

    def _build_receiver_card(self) -> QFrame:
        card = self._make_super_card(None)
        layout = card.layout()

        input_row = QHBoxLayout()
        input_row.setSpacing(Spacing.SM)

        ready_frame = QFrame()
        ready_frame.setStyleSheet(
            "background-color: #08080A; border: 1px solid #24242A; border-radius: 4px;"
        )
        ready_layout = QHBoxLayout(ready_frame)
        ready_layout.setContentsMargins(10, 6, 10, 6)
        ready_layout.setSpacing(6)

        ready_icon = QLabel()
        ready_icon.setPixmap(IconHelper.get_pixmap("zap", color="#34D399", size=12))
        ready_icon.setStyleSheet("background: transparent;")
        ready_layout.addWidget(ready_icon)

        lbl_ready = QLabel("READY")
        lbl_ready.setStyleSheet(
            "color: #34D399; font-weight: 800; font-size: 10px; font-family: monospace; background: transparent;"
        )
        ready_layout.addWidget(lbl_ready)
        input_row.addWidget(ready_frame)

        self.hardware_input = QLineEdit()
        self.hardware_input.setObjectName(ObjectNames.GP_SUPER_INPUT)
        self.hardware_input.setPlaceholderText("Scan QR code or type ID number (e.g. 261-00105)...")
        self.hardware_input.addAction(
            IconHelper.get_icon("qr-code", color=Colors.ACCENT_GOLD, size=16),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.hardware_input.returnPressed.connect(self._submit_hardware_input)
        input_row.addWidget(self.hardware_input, stretch=1)

        btn_scan = QPushButton("Scan ID")
        btn_scan.setObjectName("btn_primary")
        btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_scan.setIcon(IconHelper.get_icon("qr-code", color="#000000", size=16))
        btn_scan.setIconSize(QSize(16, 16))
        btn_scan.clicked.connect(self._submit_hardware_input)
        attach_press_feedback(btn_scan)
        input_row.addWidget(btn_scan)

        layout.addLayout(input_row)
        return card

    def _build_search_filter_row(self) -> QWidget:
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.XS)

        self._filter_button_group = QButtonGroup(self)
        self._filter_button_group.setExclusive(True)

        for label, status_key, icon_name in STATUS_FILTERS:
            btn = self._make_filter_button(label, status_key, icon_name)
            if status_key == "ALL":
                btn.setChecked(True)
            btn.clicked.connect(lambda _checked, key=status_key: self._set_status_filter(key))
            self._filter_button_group.addButton(btn)
            row.addWidget(btn)

        row.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setObjectName(ObjectNames.SEARCH_INPUT)
        self.search_input.setPlaceholderText("Search logs...")
        self.search_input.setFixedWidth(170)
        self.search_input.addAction(
            IconHelper.get_icon("search", color=Colors.TEXT_MUTED, size=14),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_input.textChanged.connect(self._apply_board_filters)
        row.addWidget(self.search_input)

        return row_widget

    def _make_filter_button(self, label: str, status_key: str, icon_name: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName(ObjectNames.FILTER_PILL)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIconSize(QSize(13, 13))

        icon_unchecked = IconHelper.get_icon(icon_name, color="#CBD5E1", size=13)
        icon_checked = IconHelper.get_icon(icon_name, color="#000000", size=13)
        btn.setIcon(icon_unchecked)

        def _sync_icon(checked: bool, _u=icon_unchecked, _c=icon_checked, _b=btn) -> None:
            _b.setIcon(_c if checked else _u)

        btn.toggled.connect(_sync_icon)
        attach_press_feedback(btn)
        return btn

    def _set_status_filter(self, status_key: str) -> None:
        if self._current_status_filter == status_key:
            return
        self._current_status_filter = status_key
        self._apply_board_filters()

    # ------------------------------------------------------------------
    # Right Sidebar Area
    # ------------------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        layout.addWidget(self._build_verification_card(), stretch=0)
        layout.addWidget(self._build_calendar_card(), stretch=1)
        layout.addWidget(self._build_summary_metrics_card(), stretch=0)

        return col

    def _build_verification_card(self) -> QFrame:
        card = self._make_super_card("Last Scan Result", decorative=True)
        card.setObjectName(ObjectNames.VERIFICATION_CARD)
        layout = card.layout()

        self.lbl_verify_icon = QLabel()
        self.lbl_verify_icon.setFixedSize(20, 20)
        self.lbl_verify_icon.setStyleSheet("background: transparent;")

        self.lbl_verify_name = QLabel("Awaiting Scan")
        self.lbl_verify_name.setStyleSheet("color: #F4EFEA; font-size: 14px; font-weight: 800;")

        self.lbl_verify_id = QLabel("—")
        self.lbl_verify_id.setStyleSheet("color: #DAA520; font-family: monospace; font-size: 10px; font-weight: 700;")

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(self.lbl_verify_icon)
        header_row.addWidget(self.lbl_verify_name)
        header_row.addStretch()
        header_row.addWidget(self.lbl_verify_id)
        layout.addLayout(header_row)

        self.lbl_verify_designation = QLabel("Scan QR code to log attendance")
        self.lbl_verify_designation.setObjectName(ObjectNames.TEXT_SECONDARY)
        layout.addWidget(self.lbl_verify_designation)

        time_box = QFrame()
        time_box.setStyleSheet("background-color: #070709; border: 1px solid #24242A; border-radius: 4px;")
        tb_layout = QHBoxLayout(time_box)
        tb_layout.setContentsMargins(8, 6, 8, 6)

        v_in = QVBoxLayout()
        lbl_in_t = QLabel("TIME IN")
        lbl_in_t.setStyleSheet("color: #8E8E93; font-size: 8px; font-family: monospace;")
        self.lbl_verify_time_in = QLabel("--:--:--")
        self.lbl_verify_time_in.setStyleSheet("color: #F4EFEA; font-size: 10px; font-weight: 700; font-family: monospace;")
        v_in.addWidget(lbl_in_t)
        v_in.addWidget(self.lbl_verify_time_in)

        v_out = QVBoxLayout()
        lbl_out_t = QLabel("TIME OUT")
        lbl_out_t.setStyleSheet("color: #8E8E93; font-size: 8px; font-family: monospace;")
        self.lbl_verify_time_out = QLabel("--:--:--")
        self.lbl_verify_time_out.setStyleSheet("color: #F4EFEA; font-size: 10px; font-weight: 700; font-family: monospace;")
        v_out.addWidget(lbl_out_t)
        v_out.addWidget(self.lbl_verify_time_out)

        tb_layout.addLayout(v_in)
        tb_layout.addLayout(v_out)
        layout.addWidget(time_box)

        self.verify_status_pill = PillWidget(
            text="READY",
            bg_color=QColor(Colors.CHIP_NEUTRAL_BG),
            text_color=QColor(Colors.TEXT_MUTED),
        )
        layout.addWidget(self.verify_status_pill)

        self._reset_verification_card()
        return card

    def _reset_verification_card(self) -> None:
        self.lbl_verify_icon.setPixmap(
            IconHelper.get_pixmap(_VERIFY_ICON_DEFAULT, color=Colors.TEXT_MUTED, size=18)
        )
        self.lbl_verify_name.setText("Awaiting Scan")
        self.lbl_verify_id.setText("—")
        self.lbl_verify_designation.setText("Scan QR code to log attendance")
        self.lbl_verify_time_in.setText("--:--:--")
        self.lbl_verify_time_out.setText("--:--:--")
        self.verify_status_pill.set_colors(QColor(Colors.CHIP_NEUTRAL_BG), QColor(Colors.TEXT_MUTED), None)
        self.verify_status_pill.set_text("READY")

    def _update_verification_card(
        self,
        full_name: str,
        id_num: str,
        designation: str,
        status_text: str,
        status_key: str,
        time_in: str,
        time_out: str,
        icon_name: str = _VERIFY_ICON_DEFAULT,
    ) -> None:
        bg, text_c, border = self._verification_status_style(status_key)

        self.lbl_verify_icon.setPixmap(IconHelper.get_pixmap(icon_name, color=text_c.name(), size=18))
        self.lbl_verify_name.setText(full_name or "—")
        self.lbl_verify_id.setText(id_num or "—")
        self.lbl_verify_designation.setText(designation or "—")
        self.lbl_verify_time_in.setText(time_in or "--:--:--")
        self.lbl_verify_time_out.setText(time_out or "--:--:--")

        self.verify_status_pill.set_colors(bg, text_c, border)
        self.verify_status_pill.set_text(status_text)

    @staticmethod
    def _verification_status_style(status_key: str):
        if status_key == "OPEN":
            return QColor(Colors.STATUS_OPEN_BG), QColor(Colors.STATUS_OPEN), QColor(Colors.STATUS_OPEN_BORDER)
        if status_key == "COMPLETED":
            return QColor(Colors.STATUS_COMPLETED_BG), QColor(Colors.STATUS_COMPLETED), QColor(Colors.STATUS_COMPLETED_BORDER)
        return QColor(Colors.CHIP_NEUTRAL_BG), QColor(Colors.TEXT_PRIMARY), None

    def _build_summary_metrics_card(self) -> QWidget:
        row = QHBoxLayout()
        row.setSpacing(Spacing.SM)

        self.lbl_gauge_total = self._build_metric_tile(row, "Total", "#F4EFEA", "layers", Colors.ACCENT_GOLD)
        self.lbl_gauge_duty = self._build_metric_tile(row, "Duty", "#80C8FF", "briefcase", "#80C8FF")
        self.lbl_gauge_visitors = self._build_metric_tile(row, "Visitors", "#F4EFEA", "users", "#34D399")

        container = QWidget()
        container.setLayout(row)
        return container

    def _build_metric_tile(
        self, parent_layout: QHBoxLayout, title: str, text_color: str, icon_name: str, accent_color: str
    ) -> QLabel:
        card = self._make_super_card(None, accent_color=accent_color)
        layout = card.layout()

        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(IconHelper.get_pixmap(icon_name, color="#8E8E93", size=10))
        icon_lbl.setStyleSheet("background: transparent;")
        title_row.addWidget(icon_lbl)

        lbl_t = QLabel(title.upper())
        lbl_t.setStyleSheet("color: #8E8E93; font-size: 8px; font-family: monospace;")
        title_row.addWidget(lbl_t)
        title_row.addStretch()

        val_lbl = QLabel("0")
        val_lbl.setStyleSheet(f"color: {text_color}; font-size: 16px; font-weight: 800; font-family: monospace;")

        layout.addLayout(title_row)
        layout.addWidget(val_lbl)
        parent_layout.addWidget(card)
        return val_lbl

    def _flash_edge_glow(self, success: bool) -> None:
        color = Colors.ACCENT_GOLD if success else Colors.DANGER_SOLID
        self._edge_glow_overlay.setStyleSheet(
            f"QFrame#edgeGlowOverlay {{ background-color: transparent; border: 4px solid {color}; }}"
        )
        self._edge_glow_anim.stop()
        self._edge_glow_effect.setOpacity(0.0)
        self._edge_glow_anim.setDuration(EDGE_GLOW_DURATION_MS)
        self._edge_glow_anim.setKeyValueAt(0.0, 0.0)
        self._edge_glow_anim.setKeyValueAt(0.5, 0.8)
        self._edge_glow_anim.setKeyValueAt(1.0, 0.0)
        self._edge_glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._edge_glow_anim.start()

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def _build_calendar_card(self) -> QFrame:
        card = self._make_super_card(None, decorative=True)
        layout = card.layout()

        layout.addWidget(self._eyebrow_label("Calendar", icon_name="calendar-check"))

        header_row = QHBoxLayout()
        header_row.setSpacing(Spacing.XS)

        self.btn_cal_prev = QPushButton()
        self.btn_cal_prev.setFixedSize(28, 28)
        self.btn_cal_prev.setStyleSheet(self._icon_button_style())
        self.btn_cal_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cal_prev.setIcon(IconHelper.get_icon("chevron-left", color=Colors.TEXT_PRIMARY, size=16))
        self.btn_cal_prev.setIconSize(QSize(16, 16))
        attach_press_feedback(self.btn_cal_prev)

        self.lbl_cal_title = QLabel("")
        self.lbl_cal_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cal_title.setStyleSheet(
            "color: #DAA520; font-weight: 800; font-size: 12px; letter-spacing: 0.6px; background: transparent;"
        )

        self.btn_cal_next = QPushButton()
        self.btn_cal_next.setFixedSize(28, 28)
        self.btn_cal_next.setStyleSheet(self._icon_button_style())
        self.btn_cal_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cal_next.setIcon(IconHelper.get_icon("chevron-right", color=Colors.TEXT_PRIMARY, size=16))
        self.btn_cal_next.setIconSize(QSize(16, 16))
        attach_press_feedback(self.btn_cal_next)

        self.btn_cal_today = QPushButton()
        self.btn_cal_today.setFixedSize(28, 28)
        self.btn_cal_today.setStyleSheet(self._icon_button_style())
        self.btn_cal_today.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cal_today.setToolTip("Jump to today")
        self.btn_cal_today.setIcon(IconHelper.get_icon("calendar-check", color=Colors.ACCENT_GOLD, size=16))
        self.btn_cal_today.setIconSize(QSize(16, 16))
        self.btn_cal_today.clicked.connect(self.jump_calendar_to_today)
        attach_press_feedback(self.btn_cal_today)

        header_row.addWidget(self.btn_cal_prev)
        header_row.addWidget(self.lbl_cal_title, stretch=1)
        header_row.addWidget(self.btn_cal_next)
        header_row.addWidget(self.btn_cal_today)
        layout.addLayout(header_row)

        self.calendar = GoldCalendar()
        self.calendar.dateSelected.connect(self._on_calendar_date_selected)
        self.calendar.pageChanged.connect(self._on_calendar_page_changed)
        self.calendar.canNavigateNextChanged.connect(self.btn_cal_next.setEnabled)

        # FIXED THIS SESSION: prev/next buttons previously had no .clicked
        # connection at all -- month navigation was completely non-functional.
        self.btn_cal_prev.clicked.connect(self.calendar.go_previous_month)
        self.btn_cal_next.clicked.connect(self.calendar.go_next_month)

        self.calendar.set_maximum_date(QDate.currentDate())
        self.calendar.set_selected_date(QDate.currentDate())
        layout.addWidget(self.calendar, stretch=1)

        # Live / viewing-past-date status strip with an explicit way back.
        status_row = QHBoxLayout()
        status_row.setSpacing(Spacing.XS)

        # FIXED THIS SESSION: this was a plain QLabel with no background/
        # padding/radius -- never actually rendered as a pill. Now reuses
        # the same PillWidget component as the verification card's status.
        self.cal_status_pill = PillWidget(
            text="LIVE",
            bg_color=QColor(Colors.STATUS_OPEN_BG),
            text_color=QColor(Colors.STATUS_OPEN),
        )
        status_row.addWidget(self.cal_status_pill)
        status_row.addStretch()

        self.btn_return_to_live = QPushButton("Back to Live")
        self.btn_return_to_live.setObjectName(ObjectNames.BTN_TONAL)
        self.btn_return_to_live.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_return_to_live.setIcon(IconHelper.get_icon("rotate-ccw", color=Colors.ACCENT_GOLD_HOVER, size=14))
        self.btn_return_to_live.setIconSize(QSize(14, 14))
        self.btn_return_to_live.clicked.connect(self._on_return_to_live_clicked)
        self.btn_return_to_live.hide()
        attach_press_feedback(self.btn_return_to_live)
        status_row.addWidget(self.btn_return_to_live)

        layout.addLayout(status_row)

        self._update_calendar_title()
        self._update_calendar_status_strip()

        return card

    def _update_calendar_title(self) -> None:
        year = self.calendar.year_shown()
        month = self.calendar.month_shown()
        self.lbl_cal_title.setText(QDate(year, month, 1).toString("MMMM yyyy").upper())

    def _update_calendar_status_strip(self) -> None:
        if self._viewing_date is None:
            self.cal_status_pill.set_colors(
                QColor(Colors.STATUS_OPEN_BG), QColor(Colors.STATUS_OPEN), QColor(Colors.STATUS_OPEN_BORDER)
            )
            self.cal_status_pill.set_text("LIVE — TODAY'S FEED")
            self.btn_return_to_live.hide()
        else:
            self.cal_status_pill.set_colors(QColor(Colors.CHIP_NEUTRAL_BG), QColor(Colors.TEXT_MUTED), None)
            self.cal_status_pill.set_text(f"VIEWING {self._viewing_date.toString('MMM d').upper()}")
            self.btn_return_to_live.show()

    def _on_return_to_live_clicked(self) -> None:
        self._return_to_live()
        self.refresh_board()

    # ------------------------------------------------------------------
    # Board Refresh & Calendar Filtering Logic
    # ------------------------------------------------------------------

    def refresh_board(self) -> None:
        stats = self.attendance_service.get_quick_stats()
        duty_cnt = stats.get("active_duty_staff", 0)
        visitors_cnt = stats.get("active_visitors", 0)

        self.lbl_gauge_duty.setText(str(duty_cnt))
        self.lbl_gauge_visitors.setText(str(visitors_cnt))
        self.lbl_gauge_total.setText(str(duty_cnt + visitors_cnt))

        self._refresh_dates_with_records()

        if self._viewing_date is not None:
            return

        feed = self.attendance_service.get_live_attendance_board_feed(limit=50)
        self._display_feed(feed)

    def force_refresh(self) -> None:
        if self._viewing_date is not None:
            self._load_board_for_date(self._viewing_date)
        self.refresh_board()
        self._show_toast("Board refreshed.", kind="info", duration_ms=1500)

    def export_attendance_csv(self) -> None:
        rows = self._last_full_feed
        if not rows:
            self._show_toast("Nothing to export — the board is currently empty.", kind="info")
            return

        default_name = f"gp_attendance_{datetime.now(PHT_TIMEZONE).strftime('%Y-%m-%d_%H%M%S')}.csv"
        with self._modal_guard():
            file_path, _ = QFileDialog.getSaveFileName(self, "Export Attendance Log", default_name, "CSV Files (*.csv)")
        if not file_path:
            return

        fieldnames = ["time_in_display", "time_out_display", "student_id_no", "full_name", "designation", "category", "status"]
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for item in rows:
                    writer.writerow({k: item.get(k, "") for k in fieldnames})
            self._show_toast(f"Exported {len(rows)} record(s).", kind="success")
        except OSError as e:
            self._show_toast(f"Export failed: {e}", kind="error", duration_ms=4000)

    def jump_calendar_to_today(self) -> None:
        # Unconditional: works regardless of which month is currently shown
        # or whether the board is already live (fixes a prior dead-end where
        # paging to a different month without selecting a date left the
        # "Today" button unable to bring the page back).
        today = QDate.currentDate()
        self.calendar.set_selected_date(today)
        self._update_calendar_title()
        if self._viewing_date is not None:
            self._viewing_date = None
            self._update_calendar_status_strip()
            self.refresh_board()

    def _display_feed(self, feed: list) -> None:
        self._last_full_feed = feed or []
        self._apply_board_filters()

    def _apply_board_filters(self) -> None:
        search_text = self.search_input.text().strip().lower()
        status_key = self._current_status_filter

        filtered = []
        for item in self._last_full_feed:
            if status_key != "ALL" and item.get("status") != status_key:
                continue
            if search_text:
                haystack = f"{item.get('full_name', '')} {item.get('student_id_no', '')}".lower()
                if search_text not in haystack:
                    continue
            filtered.append(item)

        self.board_widget.populate_feed(filtered)
        self.lbl_record_count.setText(f"Showing: {len(filtered)} entries")

    def _refresh_dates_with_records(self) -> None:
        try:
            self._dates_with_records = self.attendance_service.get_dates_with_attendance_records()
        except Exception:
            self._dates_with_records = None

        self.calendar.set_highlighted_dates(self._dates_with_records)

    def _on_calendar_page_changed(self, year: int, month: int) -> None:
        self._update_calendar_title()

    def _on_calendar_date_selected(self, date: QDate) -> None:
        today = QDate.currentDate()

        if date > today:
            self.calendar.set_selected_date(today)
            return

        if date == today:
            self._return_to_live()
            self.refresh_board()
            return

        date_str = date.toString("yyyy-MM-dd")
        if self._dates_with_records is not None and date_str not in self._dates_with_records:
            fallback_date = self._viewing_date if self._viewing_date is not None else today
            self.calendar.set_selected_date(fallback_date)
            self._show_toast(
                f"No attendance logs exist for {date.toString('MMMM d, yyyy')}.",
                kind="info",
                duration_ms=2500,
            )
            return

        self._viewing_date = date
        self.calendar.set_selected_date(date)
        self._update_calendar_status_strip()
        self._load_board_for_date(date)

    def _load_board_for_date(self, date: QDate) -> None:
        date_str = date.toString("yyyy-MM-dd")
        try:
            feed = self.attendance_service.get_attendance_board_feed_for_date(date_str)
        except Exception as e:
            self._show_toast(f"Error loading logs for {date_str}: {e}", kind="error", duration_ms=4000)
            return

        self._display_feed(feed)

    def _return_to_live(self) -> None:
        if self._viewing_date is None:
            return
        self._viewing_date = None
        self.calendar.set_selected_date(QDate.currentDate())
        self._update_calendar_status_strip()

    # ------------------------------------------------------------------
    # Input Focus & Modals
    # ------------------------------------------------------------------

    def focus_hardware_input(self) -> None:
        self.hardware_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _enforce_hardware_input_focus(self) -> None:
        if self._modal_active or not self.isVisible():
            return
        if not self.window().isActiveWindow():
            return
        if self._focus_guard_suspended:
            return

        focus_widget = QApplication.focusWidget()
        if focus_widget is self.hardware_input or focus_widget is self.search_input:
            return

        self.hardware_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _submit_hardware_input(self) -> None:
        text = self.hardware_input.text().strip()
        self.hardware_input.clear()
        if not text:
            return

        now = time.monotonic()
        if (
            self._last_scanned_payload == text
            and self._last_scan_timestamp is not None
            and (now - self._last_scan_timestamp) < QR_SCAN_DEBOUNCE_SECONDS
        ):
            return

        self._last_scanned_payload = text
        self._last_scan_timestamp = now
        self._process_scanned_payload(text)

    @contextmanager
    def _modal_guard(self):
        self._modal_active = True
        try:
            yield
        finally:
            self._modal_active = False
            QTimer.singleShot(0, self.focus_hardware_input)

    def _show_toast(self, message: str, kind: str = "success", duration_ms: int = 2600) -> None:
        if self._active_toast is not None:
            try:
                self._active_toast.dismiss_immediately()
            except RuntimeError:
                pass
            self._active_toast = None

        toast = show_toast(self, message, kind=kind, duration_ms=duration_ms)
        self._active_toast = toast
        toast.destroyed.connect(lambda: self._on_toast_destroyed(toast))

    def _on_toast_destroyed(self, toast) -> None:
        if self._active_toast is toast:
            self._active_toast = None

    def _process_scanned_payload(self, payload: str) -> None:
        try:
            eval_result = self.attendance_service.evaluate_scanned_id(payload)
            action_type = eval_result.get("type")
            now_str = datetime.now(PHT_TIMEZONE).strftime("%I:%M:%S %p")

            if action_type == "STAFF_TIME_IN_SELECT_CATEGORY":
                staff = eval_result["staff"]
                self.attendance_service.confirm_staff_time_in(staff["id"], category="Duty")
                self._flash_edge_glow(True)
                self._update_verification_card(
                    staff.get("full_name", "—"), staff.get("student_id_no", "—"),
                    staff.get("designation", "—"), "ON DUTY", "OPEN", now_str, "--:--:--",
                    icon_name="briefcase",
                )

            elif action_type == "STAFF_TIME_OUT_READY":
                staff = eval_result["staff"]
                open_session = eval_result["open_session"]
                self.attendance_service.confirm_staff_time_out(open_session["id"])
                self._flash_edge_glow(True)
                self._update_verification_card(
                    staff.get("full_name", "—"), staff.get("student_id_no", "—"),
                    staff.get("designation", "—"), "COMPLETED", "COMPLETED",
                    open_session.get("time_in_display", "--:--:--"), now_str,
                    icon_name="check-circle",
                )

            elif action_type == "GUEST_VISITOR_NEW":
                student_id = eval_result["student_id_no"]
                with self._modal_guard():
                    dialog = GuestVisitorNameDialog(student_id_no=student_id, parent=self)
                    accepted = dialog.exec() == GuestVisitorNameDialog.DialogCode.Accepted
                    visitor_name = dialog.entered_name if accepted else None
                if accepted and visitor_name:
                    self.attendance_service.confirm_visitor_time_in(student_id, visitor_name)
                    self._flash_edge_glow(True)
                    self._update_verification_card(
                        visitor_name, student_id, "Guest Visitor", "VISITING", "OPEN", now_str, "--:--:--",
                        icon_name="user-round",
                    )

            elif action_type == "VISITOR_TIME_OUT_READY":
                open_visit = eval_result["open_visit"]
                self.attendance_service.confirm_visitor_time_out(open_visit["id"])
                self._flash_edge_glow(True)
                self._update_verification_card(
                    open_visit.get("visitor_name", "—"), open_visit.get("student_id_no", "—"),
                    "Guest Visitor", "COMPLETED", "COMPLETED",
                    open_visit.get("time_in_display", "--:--:--"), now_str,
                    icon_name="check-circle",
                )

            elif action_type in ("STAFF_OVERDUE_LOCKED", "VISITOR_OVERDUE_LOCKED"):
                self._flash_edge_glow(False)
                msg = eval_result.get("message", "Session is overdue and requires administrator resolution.")
                with self._modal_guard():
                    QMessageBox.warning(self, "Overdue Session Locked", msg)

            self.refresh_board()

        except Exception as e:
            self._flash_edge_glow(False)
            with self._modal_guard():
                QMessageBox.critical(self, "Attendance Error", str(e))

    def closeEvent(self, event) -> None:
        self._board_refresh_timer.stop()
        self._focus_guard_timer.stop()
        super().closeEvent(event)