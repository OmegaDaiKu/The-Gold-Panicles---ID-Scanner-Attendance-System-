"""Unit tests verifying Admin Dashboard tabs, 22 designations dropdown, and top-level lifecycle."""

import pytest
from src.core.constants import OFFICIAL_DESIGNATIONS
from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer
from src.ui.views.admin_dashboard.dashboard_main import AdminDashboardWindow


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh temporary SQLite DatabaseConnectionManager instance."""
    db_file = tmp_path / "test_admin_dash.db"
    db_manager = DatabaseConnectionManager(str(db_file))
    schema = SchemaInitializer(db_manager)
    schema.ensure_schema_exists()
    yield db_manager
    db_manager.close()


def test_admin_dashboard_initialization_and_designations(qtbot, temp_db):
    """Verifies that AdminDashboardWindow initializes with 5 tabs and all 22 official designations."""
    admin_user = {"id": 1, "username": "admin", "role": "MASTER_ADMIN"}
    dash = AdminDashboardWindow(temp_db, admin_user=admin_user)
    qtbot.addWidget(dash)

    # 1. Verify 6 tabs exist
    assert dash.tabs.count() == 6
    assert dash.tabs.tabText(0) == "Overview"
    assert dash.tabs.tabText(1) == "Staff Directory"
    assert dash.tabs.tabText(2) == "Attendance Logs"
    assert dash.tabs.tabText(3) == "Overdue Resolution"
    assert dash.tabs.tabText(4) == "Reports & Exports"
    assert dash.tabs.tabText(5) == "Settings & Backups"

    # 2. Verify all 22 official designations are present in dropdown
    cmb_items = [
        dash.tab_staff.cmb_designation.itemText(i)
        for i in range(dash.tab_staff.cmb_designation.count())
    ]
    assert len(cmb_items) == 22
    assert cmb_items == OFFICIAL_DESIGNATIONS