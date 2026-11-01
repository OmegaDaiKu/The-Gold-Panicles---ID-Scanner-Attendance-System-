""""Main Front-Desk Kiosk Station View — Hardware QR Scanner Receiver & Log Dashboard."""

import csv
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QDate, QEvent, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from src.ui.theme import Colors, ObjectNames, Radius, Spacing, Typography
from src.ui.widgets.gold_calendar import GoldCalendar
from src.ui.widgets.pill_widget import PillWidget
from src.utils.icon_helper import IconHelper
from src.utils.time_utils import PHT_TIMEZONE, format_iso_to_pht

logger = logging.getLogger(__name__)

QR_SCAN_DEBOUNCE_SECONDS = 2.0
BOARD_AUTO_REFRESH_MS = 30_000
FOCUS_GUARD_INTERVAL_MS = 250
EDGE_GLOW_DURATION_MS = 400

STATUS_FILTERS = [
    ("All", "ALL", "list"),
    ("Active Duty (IN)", "IN", "user-check"),
    ("Overdue", "OVERDUE", "alert-triangle"),
    ("Completed (OUT)", "OUT", "check-circle"),
]

_VERIFY_ICON_DEFAULT = "qr-code"
_FOCUS_GUARD_RELEASE_DELAY_MS = 150


class StationView(QWidget):
    """Main front-desk attendance station view with dual-column layout."""

    def __init__(self, db_manager: DatabaseConnectionManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.attendance_service = AttendanceService(db_manager)

        self._viewing_date = None
        self._modal_active = False
        self._dates_with_records: Optional[set] = None

        self._last_full_feed: list = []
        self._last_filtered_feed: list = []
        self._current_status_filter: str = "ALL"

        self._last_scanned_payload = None
        self._last_scan_timestamp = None
        self._active_toast = None

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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        main_layout.setSpacing(Spacing.MD)

        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(Spacing.MD)

        cols_layout.addWidget(self._build_main_column(), 70)
        cols_layout.addWidget(self._build_sidebar(), 30)

        main_layout.addLayout(cols_layout, stretch=1)

        self._edge_glow_overlay = QFrame(self)
        self._edge_glow_overlay.setObjectName("edgeGlowOverlay")
        self._edge_glow_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._edge_glow_overlay.setStyleSheet(
            "QFrame#edgeGlowOverlay { background-color: transparent; border: none; }"
        )
        self._edge_glow_overlay.setGeometry(self.rect())
        self._edge_glow_overlay.hide()

        self._edge_glow_timer = QTimer(self)
        self._edge_glow_timer.setSingleShot(True)
        self._edge_glow_timer.timeout.connect(self._edge_glow_overlay.hide)

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
        object_name: Optional[str] = None,
    ) -> QFrame:
        card = QFrame()
        card_id = object_name or (ObjectNames.CARD_SUPER if decorative else "stationCard")
        card.setObjectName(card_id)

        border_left = f"border-left: 3px solid {accent_color};" if accent_color else ""
        card.setStyleSheet(
            f"QFrame#{card_id} {{ "
            f"background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; "
            f"border-radius: {Radius.CARD}px; {border_left} }}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.XS)

        if title:
            lbl = QLabel(title.upper())
            lbl.setStyleSheet(
                f"color: {Colors.TEXT_PRIMARY}; font-weight: 800; font-size: 10px; "
                "letter-spacing: 0.6px; background: transparent; border: none;"
            )
            layout.addWidget(lbl)
        return card

    @staticmethod
    def _icon_button_style() -> str:
        return (
            f"QPushButton {{ background-color: {Colors.SURFACE_ALT}; border: 1px solid {Colors.BORDER}; "
            f"border-radius: {Radius.BUTTON}px; padding: 0px; }} "
            f"QPushButton:hover {{ border-color: {Colors.ACCENT_GOLD}; background-color: {Colors.SURFACE}; }}"
            f"QPushButton:disabled {{ border-color: {Colors.BORDER}; color: {Colors.TEXT_MUTED}; }}"
        )

    @staticmethod
    def _eyebrow_label(text: str, icon_name: Optional[str] = None) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.XS)

        if icon_name:
            icon_lbl = QLabel()
            icon_lbl.setPixmap(IconHelper.get_pixmap(icon_name, color=Colors.TEXT_MUTED, size=12))
            icon_lbl.setStyleSheet("background: transparent; border: none;")
            row.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-weight: 800; font-size: 10px; "
            f"letter-spacing: 1px; font-family: {Typography.MONO_FAMILY}; background: transparent; border: none;"
        )
        row.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignVCenter)
        row.addStretch()
        return wrap

    def _install_focus_guard_exemptions(self) -> None:
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

    def _build_main_column(self) -> QWidget:
        col = QWidget()
        layout = QVBoxLayout(col)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        layout.addWidget(self._build_receiver_card())

        table_container = self._make_super_card(None)
        table_layout = table_container.layout()
        table_layout.addWidget(self._eyebrow_label("Attendance Activity Log", icon_name="list"))
        table_layout.addWidget(self._build_search_filter_row())

        self.board_widget = AttendanceBoardWidget()
        table_layout.addWidget(self.board_widget, stretch=1)

        footer_row = QHBoxLayout()
        self.lbl_record_count = QLabel("Showing: 0 entries")
        self.lbl_record_count.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-family: {Typography.MONO_FAMILY}; font-size: 10px; background: transparent; border: none;"
        )
        footer_row.addWidget(self.lbl_record_count, alignment=Qt.AlignmentFlag.AlignVCenter)
        footer_row.addStretch()
        table_layout.addLayout(footer_row)

        layout.addWidget(table_container, stretch=1)
        return col

    def _build_receiver_card(self) -> QFrame:
        card = self._make_super_card(None)
        layout = card.layout()

        input_row = QHBoxLayout()
        input_row.setSpacing(Spacing.SM)

        self.hardware_input = QLineEdit()
        self.hardware_input.setObjectName(ObjectNames.GP_SUPER_INPUT)
        self.hardware_input.setFixedHeight(40)
        self.hardware_input.setPlaceholderText("Scan QR code or type ID number (e.g. 261-00105)...")
        self.hardware_input.addAction(
            IconHelper.get_icon("qr-code", color=Colors.ACCENT_GOLD, size=16),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.hardware_input.returnPressed.connect(self._submit_hardware_input)
        input_row.addWidget(self.hardware_input, stretch=1)

        btn_scan = QPushButton(" Submit ID")
        btn_scan.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_scan.setFixedHeight(40)
        btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_scan.setIcon(IconHelper.get_icon("qr-code", color=Colors.BACKGROUND, size=16))
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
            row.addWidget(btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        row.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setObjectName(ObjectNames.SEARCH_INPUT)
        self.search_input.setFixedHeight(32)
        self.search_input.setPlaceholderText("Search logs...")
        self.search_input.setFixedWidth(220)
        self.search_input.addAction(
            IconHelper.get_icon("search", color=Colors.TEXT_MUTED, size=14),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_input.textChanged.connect(self._apply_board_filters)
        row.addWidget(self.search_input, alignment=Qt.AlignmentFlag.AlignVCenter)

        return row_widget

    def _make_filter_button(self, label: str, status_key: str, icon_name: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setObjectName(ObjectNames.FILTER_PILL)
        btn.setFixedHeight(32)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIconSize(QSize(13, 13))

        icon_unchecked = IconHelper.get_icon(icon_name, color=Colors.TEXT_SECONDARY, size=13)
        icon_checked = IconHelper.get_icon(icon_name, color=Colors.BACKGROUND, size=13)
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
        card = self._make_super_card("Last Scan Verification", decorative=True, object_name=ObjectNames.VERIFICATION_CARD)
        layout = card.layout()

        self.lbl_verify_icon = QLabel()
        self.lbl_verify_icon.setFixedSize(20, 20)
        self.lbl_verify_icon.setStyleSheet("background: transparent; border: none;")

        self.lbl_verify_name = QLabel("Awaiting Scan")
        self.lbl_verify_name.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 13px; font-weight: 800; background: transparent; border: none;"
        )

        self.lbl_verify_id = QLabel("—")
        self.lbl_verify_id.setStyleSheet(
            f"color: {Colors.ACCENT_GOLD}; font-family: {Typography.MONO_FAMILY}; font-size: 11px; font-weight: 700; background: transparent; border: none;"
        )

        header_row = QHBoxLayout()
        header_row.setSpacing(Spacing.XS)
        header_row.addWidget(self.lbl_verify_icon, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.lbl_verify_name, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addStretch()
        header_row.addWidget(self.lbl_verify_id, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header_row)

        self.lbl_verify_designation = QLabel("Scan QR code to log attendance")
        self.lbl_verify_designation.setObjectName(ObjectNames.TEXT_SECONDARY)
        self.lbl_verify_designation.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;"
        )
        layout.addWidget(self.lbl_verify_designation)

        time_box = QFrame()
        time_box.setObjectName("verifyTimeBox")
        time_box.setStyleSheet(
            f"QFrame#verifyTimeBox {{ background-color: {Colors.SURFACE_ALT}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.BUTTON}px; }}"
        )
        tb_layout = QHBoxLayout(time_box)
        tb_layout.setContentsMargins(Spacing.SM, Spacing.XS, Spacing.SM, Spacing.XS)

        v_in = QVBoxLayout()
        v_in.setSpacing(2)
        lbl_in_t = QLabel("TIME IN")
        lbl_in_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_in_t.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; font-family: {Typography.MONO_FAMILY}; font-weight: 700; background: transparent; border: none;"
        )
        self.lbl_verify_time_in = QLabel("--:--:--")
        self.lbl_verify_time_in.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_verify_time_in.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; font-weight: 700; font-family: {Typography.MONO_FAMILY}; background: transparent; border: none;"
        )
        v_in.addWidget(lbl_in_t)
        v_in.addWidget(self.lbl_verify_time_in)

        v_out = QVBoxLayout()
        v_out.setSpacing(2)
        lbl_out_t = QLabel("TIME OUT")
        lbl_out_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_out_t.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; font-family: {Typography.MONO_FAMILY}; font-weight: 700; background: transparent; border: none;"
        )
        self.lbl_verify_time_out = QLabel("--:--:--")
        self.lbl_verify_time_out.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_verify_time_out.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; font-weight: 700; font-family: {Typography.MONO_FAMILY}; background: transparent; border: none;"
        )
        v_out.addWidget(lbl_out_t)
        v_out.addWidget(self.lbl_verify_time_out)

        tb_layout.addLayout(v_in)
        tb_layout.addLayout(v_out)
        layout.addWidget(time_box)

        self.verify_status_pill = PillWidget(
            text="READY",
            bg_color=QColor(Colors.CHIP_NEUTRAL_BG),
            text_color=QColor(Colors.TEXT_MUTED),
            fixed_size=QSize(100, 24),
        )
        layout.addWidget(self.verify_status_pill, alignment=Qt.AlignmentFlag.AlignCenter)

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
        if status_key in ("IN", "OPEN"):
            return QColor(Colors.STATUS_IN_BG), QColor(Colors.STATUS_IN), None
        if status_key in ("OUT", "COMPLETED"):
            return QColor(Colors.STATUS_OUT_BG), QColor(Colors.STATUS_OUT), None
        return QColor(Colors.CHIP_NEUTRAL_BG), QColor(Colors.TEXT_PRIMARY), None

    def _build_summary_metrics_card(self) -> QFrame:
        """Segmented KPI Metrics Banner Card."""
        card = self._make_super_card(None, decorative=True, object_name="metricsCard")
        layout = card.layout()

        layout.addWidget(self._eyebrow_label("Desk Metrics Summary", icon_name="layers"))

        banner_box = QFrame()
        banner_box.setObjectName("metricsBannerBox")
        banner_box.setStyleSheet(
            f"QFrame#metricsBannerBox {{ background-color: {Colors.SURFACE_ALT}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.BUTTON}px; }}"
        )
        b_layout = QHBoxLayout(banner_box)
        b_layout.setContentsMargins(Spacing.XS, Spacing.SM, Spacing.XS, Spacing.SM)
        b_layout.setSpacing(0)

        # 1. Total Segment
        v_tot = QVBoxLayout()
        v_tot.setSpacing(1)
        lbl_tot = QLabel("TOTAL")
        lbl_tot.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; font-family: {Typography.MONO_FAMILY}; font-weight: 700; background: transparent; border: none;"
        )
        self.lbl_gauge_total = QLabel("0")
        self.lbl_gauge_total.setStyleSheet(
            f"color: {Colors.ACCENT_GOLD}; font-size: 18px; font-weight: 800; font-family: {Typography.MONO_FAMILY}; background: transparent; border: none;"
        )
        lbl_tot_sub = QLabel("Logs Today")
        lbl_tot_sub.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")
        v_tot.addWidget(lbl_tot, alignment=Qt.AlignmentFlag.AlignCenter)
        v_tot.addWidget(self.lbl_gauge_total, alignment=Qt.AlignmentFlag.AlignCenter)
        v_tot.addWidget(lbl_tot_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        b_layout.addLayout(v_tot, stretch=1)

        # Divider 1
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.VLine)
        div1.setStyleSheet(f"background-color: {Colors.BORDER}; max-width: 1px; border: none; margin: 0px {Spacing.XS}px;")
        b_layout.addWidget(div1)

        # 2. On Duty Segment
        v_duty = QVBoxLayout()
        v_duty.setSpacing(1)
        lbl_duty = QLabel("ON DUTY")
        lbl_duty.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; font-family: {Typography.MONO_FAMILY}; font-weight: 700; background: transparent; border: none;"
        )
        self.lbl_gauge_duty = QLabel("0")
        self.lbl_gauge_duty.setStyleSheet(
            f"color: {Colors.STATUS_IN}; font-size: 18px; font-weight: 800; font-family: {Typography.MONO_FAMILY}; background: transparent; border: none;"
        )
        lbl_duty_sub = QLabel("Active Staff")
        lbl_duty_sub.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")
        v_duty.addWidget(lbl_duty, alignment=Qt.AlignmentFlag.AlignCenter)
        v_duty.addWidget(self.lbl_gauge_duty, alignment=Qt.AlignmentFlag.AlignCenter)
        v_duty.addWidget(lbl_duty_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        b_layout.addLayout(v_duty, stretch=1)

        # Divider 2
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.VLine)
        div2.setStyleSheet(f"background-color: {Colors.BORDER}; max-width: 1px; border: none; margin: 0px {Spacing.XS}px;")
        b_layout.addWidget(div2)

        # 3. Visitors Segment
        v_vis = QVBoxLayout()
        v_vis.setSpacing(1)
        lbl_vis = QLabel("VISITORS")
        lbl_vis.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; font-size: 10px; font-family: {Typography.MONO_FAMILY}; font-weight: 700; background: transparent; border: none;"
        )
        self.lbl_gauge_visitors = QLabel("0")
        self.lbl_gauge_visitors.setStyleSheet(
            f"color: {Colors.PURPOSE_VISIT}; font-size: 18px; font-weight: 800; font-family: {Typography.MONO_FAMILY}; background: transparent; border: none;"
        )
        lbl_vis_sub = QLabel("Guest Visits")
        lbl_vis_sub.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px; background: transparent; border: none;")
        v_vis.addWidget(lbl_vis, alignment=Qt.AlignmentFlag.AlignCenter)
        v_vis.addWidget(self.lbl_gauge_visitors, alignment=Qt.AlignmentFlag.AlignCenter)
        v_vis.addWidget(lbl_vis_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        b_layout.addLayout(v_vis, stretch=1)

        layout.addWidget(banner_box)
        return card

    def _flash_edge_glow(self, success: bool) -> None:
        color = Colors.ACCENT_GOLD if success else Colors.DANGER_SOLID
        self._edge_glow_overlay.setStyleSheet(
            f"QFrame#edgeGlowOverlay {{ background-color: transparent; border: 3px solid {color}; }}"
        )
        self._edge_glow_overlay.setGeometry(self.rect())
        self._edge_glow_overlay.show()
        self._edge_glow_overlay.raise_()
        self._edge_glow_timer.start(EDGE_GLOW_DURATION_MS)

    def _build_calendar_card(self) -> QFrame:
        card = self._make_super_card(None, decorative=True, object_name="calendarCard")
        layout = card.layout()

        layout.addWidget(self._eyebrow_label("Calendar Navigation", icon_name="calendar"))

        header_row = QHBoxLayout()
        header_row.setSpacing(Spacing.XS)

        self.btn_cal_prev = QPushButton()
        self.btn_cal_prev.setFixedSize(32, 32)
        self.btn_cal_prev.setStyleSheet(self._icon_button_style())
        self.btn_cal_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cal_prev.setIcon(IconHelper.get_icon("chevron-left", color=Colors.TEXT_PRIMARY, size=14))
        self.btn_cal_prev.setIconSize(QSize(14, 14))
        attach_press_feedback(self.btn_cal_prev)

        self.lbl_cal_title = QLabel("")
        self.lbl_cal_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cal_title.setStyleSheet(
            f"color: {Colors.ACCENT_GOLD}; font-weight: 800; font-size: 11px; letter-spacing: 0.6px; background: transparent; border: none;"
        )

        self.btn_cal_next = QPushButton()
        self.btn_cal_next.setFixedSize(32, 32)
        self.btn_cal_next.setStyleSheet(self._icon_button_style())
        self.btn_cal_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cal_next.setIcon(IconHelper.get_icon("chevron-right", color=Colors.TEXT_PRIMARY, size=14))
        self.btn_cal_next.setIconSize(QSize(14, 14))
        attach_press_feedback(self.btn_cal_next)

        self.btn_cal_today = QPushButton()
        self.btn_cal_today.setFixedSize(32, 32)
        self.btn_cal_today.setStyleSheet(self._icon_button_style())
        self.btn_cal_today.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cal_today.setToolTip("Jump to today")
        self.btn_cal_today.setIcon(IconHelper.get_icon("calendar", color=Colors.ACCENT_GOLD, size=14))
        self.btn_cal_today.setIconSize(QSize(14, 14))
        self.btn_cal_today.clicked.connect(self.jump_calendar_to_today)
        attach_press_feedback(self.btn_cal_today)

        header_row.addWidget(self.btn_cal_prev, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.lbl_cal_title, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.btn_cal_next, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.btn_cal_today, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header_row)

        self.calendar = GoldCalendar()
        self.calendar.dateSelected.connect(self._on_calendar_date_selected)
        self.calendar.pageChanged.connect(self._on_calendar_page_changed)
        self.calendar.canNavigateNextChanged.connect(self.btn_cal_next.setEnabled)
        self.calendar.canNavigatePrevChanged.connect(self.btn_cal_prev.setEnabled)

        self.btn_cal_prev.clicked.connect(self.calendar.go_previous_month)
        self.btn_cal_next.clicked.connect(self.calendar.go_next_month)

        self.calendar.set_maximum_date(QDate.currentDate())
        self.calendar.set_selected_date(QDate.currentDate())
        layout.addWidget(self.calendar, stretch=1)

        status_row = QHBoxLayout()
        status_row.setSpacing(Spacing.XS)

        self.cal_status_pill = PillWidget(
            text="LIVE — TODAY'S FEED",
            bg_color=QColor(Colors.STATUS_IN_BG),
            text_color=QColor(Colors.STATUS_IN),
            fixed_size=QSize(140, 22),
        )
        status_row.addWidget(self.cal_status_pill, alignment=Qt.AlignmentFlag.AlignVCenter)
        status_row.addStretch()

        self.btn_return_to_live = QPushButton(" Back to Live")
        self.btn_return_to_live.setObjectName(ObjectNames.BTN_TONAL)
        self.btn_return_to_live.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_return_to_live.setIcon(IconHelper.get_icon("rotate-ccw", color=Colors.ACCENT_GOLD, size=12))
        self.btn_return_to_live.setIconSize(QSize(12, 12))
        self.btn_return_to_live.clicked.connect(self._on_return_to_live_clicked)
        self.btn_return_to_live.hide()
        attach_press_feedback(self.btn_return_to_live)
        status_row.addWidget(self.btn_return_to_live, alignment=Qt.AlignmentFlag.AlignVCenter)

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
                QColor(Colors.STATUS_IN_BG), QColor(Colors.STATUS_IN), None
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
        rows = self._last_filtered_feed
        if not rows:
            self._show_toast("Nothing to export — no rows match the current view.", kind="info")
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
            filter_note = "" if self._current_status_filter == "ALL" and not self.search_input.text().strip() else " (filtered view)"
            self._show_toast(f"Exported {len(rows)} record(s){filter_note}.", kind="success")
        except OSError as e:
            self._show_toast(f"Export failed: {e}", kind="error", duration_ms=4000)

    def jump_calendar_to_today(self) -> None:
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
            item_status = (item.get("status") or "").upper()
            if status_key == "IN" and item_status not in ("IN", "OPEN"):
                continue
            elif status_key == "OUT" and item_status not in ("OUT", "COMPLETED"):
                continue
            elif status_key == "OVERDUE" and item_status != "OVERDUE":
                continue

            if search_text:
                haystack = f"{item.get('full_name', '')} {item.get('student_id_no', '')}".lower()
                if search_text not in haystack:
                    continue
            filtered.append(item)

        self._last_filtered_feed = filtered
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
        if focus_widget is self.hardware_input:
            return

        if focus_widget is self.search_input:
            return

        if self.hardware_input.text():
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

        # Parent to main window to prevent internal child container geometry clipping
        parent_target = self.window() if self.window() is not None else self
        # A toast is purely cosmetic feedback. If it fails to build, log it and move on
        # so the scan/export workflow (and its own error handler) is never interrupted.
        try:
            toast = show_toast(parent_target, message, kind=kind, duration_ms=duration_ms)
        except Exception:
            logger.exception("Failed to display toast notification: %s", message)
            return
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

            # Guaranteed auto-return to live mode so current check-ins appear on screen immediately
            self._return_to_live()

            if action_type in ("STAFF_TIME_IN_READY", "STAFF_TIME_IN_SELECT_CATEGORY"):
                staff = eval_result["staff"]
                self.attendance_service.confirm_staff_time_in(staff["id"], category="Duty")
                self._flash_edge_glow(True)
                self._update_verification_card(
                    staff.get("full_name", "—"), staff.get("student_id_no", "—"),
                    staff.get("designation", "—"), "IN", "IN", now_str, "--:--:--",
                    icon_name="briefcase",
                )
                self._show_toast(f"Time In: {staff.get('full_name')} (On Duty)", kind="success")

            elif action_type == "STAFF_TIME_OUT_READY":
                staff = eval_result["staff"]
                open_session = eval_result["open_session"]
                self.attendance_service.confirm_staff_time_out(open_session["id"])
                self._flash_edge_glow(True)

                raw_time_in = open_session.get("time_in")
                time_in_str = format_iso_to_pht(raw_time_in) if raw_time_in else open_session.get("time_in_display", "--:--:--")

                self._update_verification_card(
                    staff.get("full_name", "—"), staff.get("student_id_no", "—"),
                    staff.get("designation", "—"), "OUT", "OUT",
                    time_in_str, now_str,
                    icon_name="check-circle",
                )
                self._show_toast(f"Time Out: {staff.get('full_name')}", kind="success")

            elif action_type in ("STAFF_TIME_OUT_COOLDOWN", "VISITOR_TIME_OUT_COOLDOWN"):
                self._flash_edge_glow(False)
                remaining = eval_result.get("seconds_remaining", 1)
                self._show_toast(f"Cooldown active: please wait {remaining}s before timing out.", kind="error")

            elif action_type == "INACTIVE_STAFF":
                self._flash_edge_glow(False)
                msg = eval_result.get("message", "Staff account is deactivated.")
                self._show_toast(msg, kind="error")

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
                        visitor_name, student_id, "Guest Visitor", "IN", "IN", now_str, "--:--:--",
                        icon_name="user-check",
                    )
                    self._show_toast(f"Visitor Time In: {visitor_name}", kind="success")

            elif action_type == "VISITOR_TIME_OUT_READY":
                open_visit = eval_result["open_visit"]
                self.attendance_service.confirm_visitor_time_out(open_visit["id"])
                self._flash_edge_glow(True)

                raw_time_in = open_visit.get("time_in")
                time_in_str = format_iso_to_pht(raw_time_in) if raw_time_in else open_visit.get("time_in_display", "--:--:--")

                self._update_verification_card(
                    open_visit.get("visitor_name", "—"), open_visit.get("student_id_no", "—"),
                    "Guest Visitor", "OUT", "OUT",
                    time_in_str, now_str,
                    icon_name="check-circle",
                )
                self._show_toast(f"Visitor Time Out: {open_visit.get('visitor_name', 'Visitor')}", kind="success")

            elif action_type in ("STAFF_OVERDUE_LOCKED", "VISITOR_OVERDUE_LOCKED"):
                self._flash_edge_glow(False)
                msg = eval_result.get("message", "Session is overdue and requires administrator resolution.")
                self._show_toast(msg, kind="error", duration_ms=4000)

            self.refresh_board()

        except Exception as e:
            self._flash_edge_glow(False)
            self._show_toast(f"Error: {e}", kind="error", duration_ms=4000)

    def closeEvent(self, event) -> None:
        self._board_refresh_timer.stop()
        self._focus_guard_timer.stop()
        super().closeEvent(event)