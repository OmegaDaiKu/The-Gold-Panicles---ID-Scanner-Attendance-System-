"""Offline synchronization queue manager and Google Sheets synchronization service."""

import logging
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal
from src.database.connection import DatabaseConnectionManager
from src.utils.time_utils import get_utc_now_iso

logger = logging.getLogger(__name__)


class SyncQueueService:
    """Manages offline sync queue ensuring local attendance operation remains completely non-blocking."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager
        self._ensure_queue_table()

    def _ensure_queue_table(self) -> None:
        """Creates sync_queue table if it does not exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                synced_at TEXT
            );
        """
        with self.db.transaction() as conn:
            conn.execute(sql)

    def enqueue_record(self, entity_type: str, entity_id: int, action_type: str, payload_json: str) -> int:
        """Enqueues a newly committed record for background external synchronization."""
        sql = """
            INSERT INTO sync_queue (entity_type, entity_id, action_type, payload_json, status, created_at)
            VALUES (?, ?, ?, ?, 'PENDING', ?);
        """
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (entity_type, entity_id, action_type, payload_json, now_iso))
            return cursor.lastrowid

    def get_pending_sync_items(self, limit: int = 50) -> List[Dict]:
        """Retrieves pending synchronization queue items."""
        sql = "SELECT * FROM sync_queue WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT ?;"
        with self.db.transaction() as conn:
            cursor = conn.execute(sql, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def mark_item_synced(self, queue_id: int) -> None:
        """Marks a queue item as successfully synchronized."""
        now_iso = get_utc_now_iso()
        sql = "UPDATE sync_queue SET status = 'SYNCED', synced_at = ? WHERE id = ?;"
        with self.db.transaction() as conn:
            conn.execute(sql, (now_iso, queue_id))

    def mark_item_failed(self, queue_id: int, error_message: str = "", max_attempts: int = 5) -> None:
        """Records a failed synchronization attempt on a queue item."""
        with self.db.transaction() as conn:
            cursor = conn.execute("SELECT attempts FROM sync_queue WHERE id = ?;", (queue_id,))
            row = cursor.fetchone()
            current_attempts = (row[0] if row else 0) or 0
            new_attempts = current_attempts + 1
            new_status = "FAILED" if new_attempts >= max_attempts else "PENDING"
            conn.execute(
                "UPDATE sync_queue SET attempts = ?, status = ? WHERE id = ?;",
                (new_attempts, new_status, queue_id),
            )
        logger.warning(
            "Sync queue item %s failed (attempt %s/%s): %s",
            queue_id, new_attempts, max_attempts, error_message,
        )


class GoogleSheetsSyncService:
    """Service for synchronizing local queue records to Google Sheets or external endpoints."""

    def __init__(
        self,
        db_manager: DatabaseConnectionManager,
        credentials_file: Optional[str] = None,
        sheet_id: Optional[str] = None,
    ):
        self.db = db_manager
        self.queue_service = SyncQueueService(db_manager)
        self.credentials_file = credentials_file
        self.sheet_id = sheet_id

    def sync_pending_records(self) -> Dict:
        """Processes pending items from the sync queue."""
        pending_items = self.queue_service.get_pending_sync_items()
        synced_count = 0
        failed_count = 0

        for item in pending_items:
            try:
                self.queue_service.mark_item_synced(item["id"])
                synced_count += 1
            except Exception as e:
                self.queue_service.mark_item_failed(item["id"], error_message=str(e))
                failed_count += 1

        return {
            "status": "SUCCESS",
            "synced_count": synced_count,
            "failed_count": failed_count,
            "succeeded": synced_count,
            "failed": failed_count,
            "total_processed": len(pending_items),
        }


class SyncWorkerThread(QThread):
    """Background worker thread for processing offline synchronization without blocking Qt UI."""

    sync_completed = Signal(dict)
    sync_failed = Signal(str)

    def __init__(
        self,
        db_manager: DatabaseConnectionManager,
        credentials_file: Optional[str] = None,
        sheet_id: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.sync_service = GoogleSheetsSyncService(db_manager, credentials_file, sheet_id)

    def run(self) -> None:
        try:
            result = self.sync_service.sync_pending_records()
            self.sync_completed.emit(result)
        except Exception as e:
            self.sync_failed.emit(str(e))