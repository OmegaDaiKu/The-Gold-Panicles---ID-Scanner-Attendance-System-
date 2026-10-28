"""Unit tests for PySide6 UI modal dialogs and attendance board rendering."""

import pytest
from PySide6.QtCore import Qt
from src.ui.components.modals import CategorySelectionDialog, GuestVisitorNameDialog
from src.ui.components.attendance_board import AttendanceBoardWidget


def test_category_selection_dialog(qtbot):
    """Verifies category selection modal button click interactions."""
    dialog = CategorySelectionDialog("Jules Leo Reserva", "Editor-in-Chief")
    qtbot.addWidget(dialog)

    # Click Duty
    duty_btn = dialog.findChild(type(dialog.findChildren(type(dialog.children()[0]))[0]))
    dialog._select("Duty")

    assert dialog.selected_category == "Duty"


def test_attendance_board_populates_feed(qtbot):
    """Verifies that AttendanceBoardWidget creates separate Time In and Time Out cells."""
    board = AttendanceBoardWidget()
    qtbot.addWidget(board)

    sample_feed = [
        {
            "id": 1,
            "student_id_no": "261-00105",
            "full_name": "Jules Leo Reserva",
            "designation": "Editor-in-Chief",
            "category": "Duty",
            "time_in_display": "10:57:41 PM",
            "time_out_display": "11:30:00 PM",
            "status": "COMPLETED",
        }
    ]

    board.populate_feed(sample_feed)
    assert board.table.rowCount() == 1
    assert board.table.item(0, 1).text() == "10:57:41 PM"  # Time In
    assert board.table.item(0, 2).text() == "11:30:00 PM"  # Time Out
    assert board.table.item(0, 5).text() == "Editor-in-Chief"  # Designation


def test_camera_preview_widget_updates(qtbot):
    """Verifies CameraPreviewWidget status and counter updates."""
    from src.ui.components.camera_preview import CameraPreviewWidget
    preview = CameraPreviewWidget()
    qtbot.addWidget(preview)

    preview.update_status("Active • Scanning")
    assert preview.lbl_status.text() == "Active • Scanning"

    preview.update_counts(3, 2)
    assert preview.lbl_duty_count.text() == "Duty: 3"
    assert preview.lbl_visitor_count.text() == "Visitors: 2"


def test_main_window_initialization(qtbot, tmp_path):
    """Verifies MainWindow mounts StationView and initializes properly."""
    from src.database.connection import DatabaseConnectionManager
    from src.database.schema import SchemaInitializer
    from src.ui.main_window import MainWindow

    db_file = tmp_path / "test_main_win.db"
    db_mgr = DatabaseConnectionManager(str(db_file))
    SchemaInitializer(db_mgr).ensure_schema_exists()

    win = MainWindow(db_mgr)
    qtbot.addWidget(win)

    assert win.windowTitle() == "The Gold Panicles — QR Attendance System"
    assert hasattr(win, "station_view")
    assert win.centralWidget() is not None

    if hasattr(win.station_view, "camera_thread"):
        win.station_view.camera_thread.stop()
    db_mgr.close()