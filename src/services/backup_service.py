""""Native SQLite database hot-backup service using the online backup API."""

import logging
import sqlite3
from pathlib import Path
from typing import Dict, Optional, List
from src.database.connection import DatabaseConnectionManager
from src.database.repositories.audit_repo import AuditRepository
from src.utils.time_utils import get_utc_now_iso

logger = logging.getLogger(__name__)


class BackupService:
    """Manages online SQLite hot database backups without locking active transactions."""

    def __init__(self, db_manager: DatabaseConnectionManager, backup_dir: str = "backups"):
        self.db = db_manager
        self.audit_repo = AuditRepository(db_manager)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, admin_id: Optional[int] = None, trigger_reason: Optional[str] = None) -> Dict:
        """Creates a timestamped native SQLite hot backup file."""
        now_iso = get_utc_now_iso()
        timestamp_str = now_iso.replace(":", "-").replace(".", "-")
        backup_filename = f"tgp_attendance_backup_{timestamp_str}.db"
        dest_path = self.backup_dir / backup_filename

        src_conn = self.db.get_connection()
        dest_conn = sqlite3.connect(str(dest_path))

        backup_completed = False
        file_size_bytes = 0

        try:
            with self.db.reader_lock():
                with dest_conn:
                    src_conn.backup(dest_conn)
            backup_completed = True

            file_size_bytes = dest_path.stat().st_size
            dest_conn.close()
            dest_conn = None

        except Exception as e:
            if dest_conn:
                dest_conn.close()
                dest_conn = None
            if not backup_completed and dest_path.exists():
                try:
                    dest_path.unlink()
                except OSError:
                    pass
            raise RuntimeError(f"Database backup failed: {str(e)}") from e
        finally:
            if dest_conn:
                dest_conn.close()

        # FIXED THIS SESSION (same bug class as the H5 audit_id truthy-check
        # fix applied to directory_service.py): `if admin_id:` would silently
        # skip audit logging if admin_id were ever 0. Changed to `is not None`
        # for consistency, even though admin IDs are autoincrement from 1 in
        # every admin-creation path seen so far.
        if admin_id is not None:
            try:
                reason_text = trigger_reason if trigger_reason else f"Created database hot-backup: {backup_filename}"
                self.audit_repo.log_action(
                    admin_id=admin_id,
                    action_type="CREATE_BACKUP",
                    entity_type="database",
                    entity_id=0,
                    reason=reason_text,
                    old_values=None,
                    new_values={"filename": backup_filename, "size_bytes": file_size_bytes},
                    timestamp=now_iso,
                )
            except Exception as audit_err:
                logger.warning(
                    "Backup '%s' was created successfully, but its audit log entry "
                    "failed to write: %s",
                    backup_filename,
                    audit_err,
                )

        return {
            "status": "SUCCESS",
            "filename": backup_filename,
            "file_path": str(dest_path),
            "size_bytes": file_size_bytes,
            "timestamp": now_iso,
        }

    def create_hot_backup(self, admin_id: Optional[int] = None) -> str:
        """Creates a hot backup and returns the file path string."""
        res = self.create_backup(admin_id=admin_id)
        return res["file_path"]

    def list_backups(self) -> List[Dict]:
        """Lists all available local database backups."""
        from datetime import datetime, timezone
        backups = []
        for p in self.backup_dir.glob("*.db"):
            try:
                stat = p.stat()
                mtime_str = datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%d %I:%M:%S %p")
                backups.append({
                    "filename": p.name,
                    "file_path": str(p),
                    "size_bytes": stat.st_size,
                    "created_at": mtime_str,
                    "mtime": stat.st_mtime,
                })
            except OSError:
                pass
        backups.sort(key=lambda x: x["mtime"], reverse=True)
        return backups

    def _validate_backup_file(self, path: Path) -> None:
        """Performs a lightweight integrity check on a candidate backup file."""
        try:
            check_conn = sqlite3.connect(str(path))
            try:
                cursor = check_conn.execute("PRAGMA quick_check;")
                result = cursor.fetchone()
                if not result or result[0] != "ok":
                    raise RuntimeError(
                        f"Backup file failed integrity check (PRAGMA quick_check): {result}"
                    )
            finally:
                check_conn.close()
        except sqlite3.DatabaseError as e:
            raise RuntimeError(f"Selected file is not a valid SQLite database: {e}") from e

    def restore_backup(self, backup_file_path: str, admin_id: Optional[int] = None) -> bool:
        """Restores the active database from a specified backup file after creating a safety snapshot.

        FLAGGED, NOT CHANGED THIS PASS: this acquires self.db.writer_lock()
        and then, still on the same thread, calls self.create_backup() which
        internally acquires self.db.reader_lock(). Whether this nested
        writer-then-reader acquisition on the same thread is safe depends
        entirely on _ReadersWriterLock's actual implementation in
        connection.py (fixed earlier this session for an unrelated
        cross-thread release bug, C2) -- I have not re-read that class this
        turn and am not asserting this deadlocks, only that I can't confirm
        it doesn't without seeing it again.
        """
        target_path = Path(backup_file_path)
        if not target_path.exists():
            raise FileNotFoundError(f"Backup file not found at {backup_file_path}")

        self._validate_backup_file(target_path)

        with self.db.writer_lock():
            self.create_backup(
                admin_id=admin_id,
                trigger_reason="Automatic safety snapshot captured prior to a database restore",
            )

            src_conn = sqlite3.connect(str(target_path))
            dest_conn = self.db.get_connection()
            try:
                with dest_conn:
                    src_conn.backup(dest_conn)
                # FIXED THIS SESSION: same `if admin_id:` -> `is not None` fix
                # as create_backup() above.
                if admin_id is not None:
                    self.audit_repo.log_action(
                        admin_id=admin_id,
                        action_type="RESTORE_BACKUP",
                        entity_type="database",
                        entity_id=0,
                        reason=f"Restored database from: {target_path.name}",
                        timestamp=get_utc_now_iso(),
                    )
                return True
            finally:
                src_conn.close()