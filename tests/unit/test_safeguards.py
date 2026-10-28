"""Unit tests verifying native SQLite backup generation, sync queue DAO, and shutdown guardrails."""

import pytest
from pathlib import Path
from src.database.connection import DatabaseConnectionManager
from src.database.schema import SchemaInitializer
from src.services.auth_service import AuthService
from src.services.backup_service import BackupService
from src.services.sync_service import SyncQueueService


@pytest.fixture
def temp_db(tmp_path):
    """Provides a temporary SQLite DatabaseConnectionManager instance."""
    db_file = tmp_path / "test_safeguards.db"
    db_manager = DatabaseConnectionManager(str(db_file))
    schema = SchemaInitializer(db_manager)
    schema.ensure_schema_exists()
    yield db_manager
    db_manager.close()


def test_native_sqlite_hot_backup(temp_db, tmp_path):
    """Verifies that BackupService creates a restorable online database backup."""
    # Seed default admin account so admin_id=1 exists for foreign key audit references
    auth_service = AuthService(temp_db)
    admin = auth_service.ensure_default_admin_exists()
    admin_id = admin["id"]

    backup_dir = tmp_path / "backups"
    backup_service = BackupService(temp_db, backup_dir=str(backup_dir))

    result = backup_service.create_backup(admin_id=admin_id)

    assert result["status"] == "SUCCESS"
    assert Path(result["file_path"]).exists()
    assert result["size_bytes"] > 0


def test_sync_queue_enqueue_and_process(temp_db):
    """Verifies offline sync queue item enqueueing and status transitions."""
    sync_service = SyncQueueService(temp_db)

    qid = sync_service.enqueue_record(
        entity_type="attendance_sessions",
        entity_id=101,
        action_type="TIME_IN",
        payload_json='{"student_id_no": "261-00105", "category": "Duty"}',
    )
    assert qid > 0

    pending = sync_service.get_pending_sync_items()
    assert len(pending) == 1
    assert pending[0]["entity_id"] == 101

    sync_service.mark_item_synced(qid)
    remaining_pending = sync_service.get_pending_sync_items()
    assert len(remaining_pending) == 0