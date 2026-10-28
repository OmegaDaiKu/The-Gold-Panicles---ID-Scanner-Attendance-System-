"""Unit tests verifying SQLite hot-backup listing and Google Sheets sync outbox processing."""

import pytest
from pathlib import Path
from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer
from src.services.auth_service import AuthService
from src.services.backup_service import BackupService
from src.services.sync_service import GoogleSheetsSyncService, SyncQueueService


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh temporary SQLite DatabaseConnectionManager instance."""
    db_file = tmp_path / "test_sync_backup.db"
    db_manager = DatabaseConnectionManager(str(db_file))
    schema = SchemaInitializer(db_manager)
    schema.ensure_schema_exists()
    yield db_manager
    db_manager.close()


def test_backup_service_list_and_create(temp_db, tmp_path):
    """Verifies that BackupService creates backups and lists them correctly."""
    auth_service = AuthService(temp_db)
    admin = auth_service.ensure_default_admin_exists()

    backup_dir = tmp_path / "backups"
    backup_service = BackupService(temp_db, backup_dir=str(backup_dir))

    # Initial list is empty
    assert len(backup_service.list_backups()) == 0

    # Create backup via create_hot_backup
    backup_path = backup_service.create_hot_backup(admin_id=admin["id"])
    assert Path(backup_path).exists()

    # Verify backup is in list
    backups = backup_service.list_backups()
    assert len(backups) == 1
    assert backups[0]["filename"] == Path(backup_path).name
    assert backups[0]["size_bytes"] > 0


def test_sync_service_process_records(temp_db):
    """Verifies that GoogleSheetsSyncService processes and marks queued records."""
    queue_service = SyncQueueService(temp_db)
    sync_service = GoogleSheetsSyncService(temp_db)

    # Enqueue a dummy record
    qid = queue_service.enqueue_record(
        entity_type="attendance_sessions",
        entity_id=1,
        action_type="TIME_IN",
        payload_json='{"test": true}',
    )
    assert qid > 0

    # Run sync
    res = sync_service.sync_pending_records()
    assert res["status"] == "SUCCESS"
    assert res["succeeded"] == 1
    assert res["failed"] == 0

    # Ensure queue is now empty
    pending = queue_service.get_pending_sync_items()
    assert len(pending) == 0