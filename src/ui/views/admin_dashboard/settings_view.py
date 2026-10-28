""""System settings, manual backup trigger, and Google Sheets sync management view."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.exceptions import TGPError
from src.database.repositories.audit_repo import AuditRepository
from src.services.backup_service import BackupService
from src.services.sync_service import GoogleSheetsSyncService, SyncWorkerThread
from src.ui.theme import ObjectNames
from src.utils.time_utils import get_utc_now_iso


class SettingsViewTab(QWidget):
    """Admin settings panel for database backups and Google Sheets synchronization."""

    def __init__(self, db_manager, admin_id: int, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager

        if admin_id is None:
            raise ValueError(
                "SettingsViewTab requires a valid 'admin_id' for audit-trail attribution. "
                "Received: {!r}".format(admin_id)
            )
        self.admin_id = admin_id

        self.backup_service = BackupService(db_manager)
        self.sync_service = GoogleSheetsSyncService(db_manager)
        self.audit_repo = AuditRepository(db_manager)
        self.worker = None

        self._init_ui()
        self.refresh_backups_list()

    def _log_action(self, action_type: str, entity_type: str, reason: str, new_values: dict | None) -> bool:
        try:
            self.audit_repo.log_action(
                admin_id=self.admin_id,
                action_type=action_type,
                entity_type=entity_type,
                entity_id=0,
                reason=reason,
                old_values=None,
                new_values=new_values,
                timestamp=get_utc_now_iso(),
            )
            return True
        except Exception:
            return False

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        lbl_header = QLabel("SYSTEM SETTINGS, BACKUPS & GOOGLE SHEETS SYNC")
        lbl_header.setObjectName(ObjectNames.SECTION_TITLE)
        layout.addWidget(lbl_header)

        # Google Sheets Sync Group
        sync_group = QGroupBox("Google Sheets Synchronization Outbox")
        sync_layout = QVBoxLayout(sync_group)

        self.lbl_sync_status = QLabel("Outbox Queue Status: Ready")
        sync_layout.addWidget(self.lbl_sync_status)

        self.btn_sync = QPushButton("SYNC OUTBOX NOW")
        self.btn_sync.setObjectName(ObjectNames.BTN_PRIMARY)
        self.btn_sync.clicked.connect(self._handle_manual_sync)
        sync_layout.addWidget(self.btn_sync)

        layout.addWidget(sync_group)

        # Database Backup & Restore Group
        backup_group = QGroupBox("SQLite Local Hot Backups & Safe Restoration")
        backup_layout = QVBoxLayout(backup_group)

        btn_backup_now = QPushButton("CREATE HOT BACKUP NOW")
        btn_backup_now.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_backup_now.clicked.connect(self._handle_create_backup)
        backup_layout.addWidget(btn_backup_now)

        self.table_backups = QTableWidget()
        self.table_backups.setColumnCount(3)
        self.table_backups.setHorizontalHeaderLabels(["Filename", "Size (KB)", "Created At"])
        self.table_backups.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        backup_layout.addWidget(self.table_backups)

        btn_restore = QPushButton("RESTORE SELECTED BACKUP FILE")
        btn_restore.setObjectName(ObjectNames.BTN_CANCEL)
        btn_restore.clicked.connect(self._handle_restore_backup)
        backup_layout.addWidget(btn_restore)

        layout.addWidget(backup_group)

    def refresh_backups_list(self) -> None:
        try:
            backups = self.backup_service.list_backups()
        except Exception as e:
            self.table_backups.setRowCount(0)
            QMessageBox.warning(
                self,
                "Backup List Error",
                f"Could not load the list of existing backups:\n{e}",
            )
            return

        self.table_backups.setRowCount(len(backups))
        for row, b in enumerate(backups):
            self.table_backups.setItem(row, 0, QTableWidgetItem(b.get("filename", "")))
            size_bytes = b.get("size_bytes", 0) or 0
            size_kb = round(size_bytes / 1024, 1)
            self.table_backups.setItem(row, 1, QTableWidgetItem(f"{size_kb} KB"))
            self.table_backups.setItem(row, 2, QTableWidgetItem(b.get("created_at", "")))

    def _handle_manual_sync(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self,
                "Sync In Progress",
                "A Google Sheets sync is already running in the background. Please wait for it to finish.",
            )
            return

        self.btn_sync.setEnabled(False)
        self.lbl_sync_status.setText("Outbox Queue Status: Syncing in background...")

        self._log_action(
            action_type="SYNC",
            entity_type="google_sheets_sync",
            reason="Triggered a manual Google Sheets outbox sync.",
            new_values=None,
        )

        self.worker = SyncWorkerThread(self.db_manager, parent=self)
        self.worker.sync_completed.connect(self._on_sync_completed)
        self.worker.finished.connect(self._on_sync_thread_finished)
        self.worker.start()

    def _on_sync_thread_finished(self) -> None:
        self.btn_sync.setEnabled(True)
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def _on_sync_completed(self, result: dict) -> None:
        succeeded = result.get("succeeded", "?")
        failed = result.get("failed", "?")
        msg = f"Sync Completed: {succeeded} succeeded, {failed} failed."
        self.lbl_sync_status.setText(f"Outbox Queue Status: {msg}")
        QMessageBox.information(self, "Google Sheets Sync", msg)

    def _handle_create_backup(self) -> None:
        try:
            filepath = self.backup_service.create_hot_backup()
            self.refresh_backups_list()

            audit_ok = self._log_action(
                action_type="BACKUP_CREATE",
                entity_type="database_backup",
                reason=f"Created a manual hot backup: {filepath}",
                new_values={"filepath": str(filepath)},
            )

            msg = f"Hot backup created:\n{filepath}"
            if not audit_ok:
                msg += "\n\n(Note: this action could not be recorded in the audit trail.)"
            QMessageBox.information(self, "Backup Success", msg)
        except TGPError as e:
            QMessageBox.warning(self, "Backup Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Unexpected Backup Error", f"An unexpected error occurred:\n{e}")

    def _handle_restore_backup(self) -> None:
        selected = self.table_backups.selectedItems()
        if not selected:
            QMessageBox.information(self, "Selection Required", "Please select a backup file from the list to restore.")
            return

        row = selected[0].row()
        filename = self.table_backups.item(row, 0).text()
        filepath = str(self.backup_service.backup_dir / filename)

        confirm = QMessageBox.warning(
            self,
            "Confirm Database Restoration",
            f"Are you sure you want to restore '{filename}'?\n\nA safety recovery snapshot of the active database will be created automatically before overwriting.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.backup_service.restore_backup(filepath)

                audit_ok = self._log_action(
                    action_type="BACKUP_RESTORE",
                    entity_type="database_backup",
                    reason=f"Restored the live database from backup file: {filename}",
                    new_values={"filepath": filepath},
                )

                msg = "Database restored successfully."
                if not audit_ok:
                    msg += "\n\n(Note: this restoration could not be recorded in the audit trail.)"
                QMessageBox.information(self, "Restoration Complete", msg)
                self.refresh_backups_list()
            except TGPError as e:
                QMessageBox.critical(self, "Restoration Failed", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Unexpected Restoration Error", f"An unexpected error occurred:\n{e}")