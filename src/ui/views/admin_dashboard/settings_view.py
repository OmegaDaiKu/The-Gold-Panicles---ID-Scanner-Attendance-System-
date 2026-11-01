"""System settings, manual backup trigger, and Google Sheets sync management view."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
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
from src.ui.components.animations import attach_press_feedback
from src.ui.theme import Colors, ObjectNames, Radius, Spacing
from src.utils.icon_helper import IconHelper
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
        layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        layout.setSpacing(Spacing.MD)

        # Header Card
        header_card = QFrame()
        header_card.setObjectName(ObjectNames.SURFACE_CARD)
        header_card.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px; }}"
        )
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        header_layout.setSpacing(Spacing.XS)

        title_row = QHBoxLayout()
        title_row.setSpacing(Spacing.XS)

        icon_title = QLabel()
        icon_title.setPixmap(IconHelper.get_pixmap("settings", color=Colors.ACCENT_GOLD, size=18))
        icon_title.setStyleSheet("background: transparent;")
        title_row.addWidget(icon_title)

        lbl_header = QLabel("SYSTEM SETTINGS, BACKUPS & GOOGLE SHEETS SYNC")
        lbl_header.setObjectName(ObjectNames.SECTION_TITLE)
        lbl_header.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 14px; font-weight: 800; letter-spacing: 0.8px; background: transparent;"
        )
        title_row.addWidget(lbl_header)
        title_row.addStretch()

        header_layout.addLayout(title_row)

        desc = QLabel(
            "Manage local SQLite hot database backups, trigger background synchronization with Google Sheets outbox, "
            "and execute safe database restorations."
        )
        desc.setObjectName(ObjectNames.TEXT_SECONDARY)
        desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        desc.setWordWrap(True)

        header_layout.addWidget(desc)
        layout.addWidget(header_card)

        # Google Sheets Sync Group
        sync_card = QFrame()
        sync_card.setObjectName(ObjectNames.SURFACE_CARD)
        sync_card.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px; }}"
        )
        sync_layout = QVBoxLayout(sync_card)
        sync_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        sync_layout.setSpacing(Spacing.SM)

        sync_header = QHBoxLayout()
        sync_header.setSpacing(Spacing.XS)

        icon_cloud = QLabel()
        icon_cloud.setPixmap(IconHelper.get_pixmap("cloud", color=Colors.ACCENT_GOLD, size=16))
        icon_cloud.setStyleSheet("background: transparent;")
        sync_header.addWidget(icon_cloud)

        lbl_sync_title = QLabel("Google Sheets Synchronization Outbox")
        lbl_sync_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 13px; font-weight: 700; background: transparent;")
        sync_header.addWidget(lbl_sync_title)
        sync_header.addStretch()

        sync_layout.addLayout(sync_header)

        self.lbl_sync_status = QLabel("Outbox Queue Status: Ready")
        self.lbl_sync_status.setObjectName(ObjectNames.TEXT_SECONDARY)
        self.lbl_sync_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        sync_layout.addWidget(self.lbl_sync_status)

        self.btn_sync = QPushButton(" SYNC OUTBOX NOW")
        self.btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sync.setObjectName(ObjectNames.BTN_PRIMARY)
        self.btn_sync.setIcon(IconHelper.get_icon("refresh-cw", color=Colors.BACKGROUND, size=14))
        self.btn_sync.setIconSize(QSize(14, 14))
        self.btn_sync.clicked.connect(self._handle_manual_sync)
        attach_press_feedback(self.btn_sync)

        sync_layout.addWidget(self.btn_sync, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(sync_card)

        # Database Backup & Restore Group
        backup_card = QFrame()
        backup_card.setObjectName(ObjectNames.SURFACE_CARD)
        backup_card.setStyleSheet(
            f"QFrame#{ObjectNames.SURFACE_CARD} {{ background-color: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; border-radius: {Radius.CARD}px; }}"
        )
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        backup_layout.setSpacing(Spacing.SM)

        backup_header = QHBoxLayout()
        backup_header.setSpacing(Spacing.XS)

        icon_db = QLabel()
        icon_db.setPixmap(IconHelper.get_pixmap("database", color=Colors.ACCENT_GOLD, size=16))
        icon_db.setStyleSheet("background: transparent;")
        backup_header.addWidget(icon_db)

        lbl_backup_title = QLabel("SQLite Local Hot Backups & Safe Restoration")
        lbl_backup_title.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 13px; font-weight: 700; background: transparent;")
        backup_header.addWidget(lbl_backup_title)
        backup_header.addStretch()

        backup_layout.addLayout(backup_header)

        btn_backup_now = QPushButton(" CREATE HOT BACKUP NOW")
        btn_backup_now.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_backup_now.setObjectName(ObjectNames.BTN_PRIMARY)
        btn_backup_now.setIcon(IconHelper.get_icon("plus-circle", color=Colors.BACKGROUND, size=14))
        btn_backup_now.setIconSize(QSize(14, 14))
        btn_backup_now.clicked.connect(self._handle_create_backup)
        attach_press_feedback(btn_backup_now)
        backup_layout.addWidget(btn_backup_now, alignment=Qt.AlignmentFlag.AlignLeft)

        self.table_backups = QTableWidget()
        self.table_backups.setColumnCount(3)
        self.table_backups.setHorizontalHeaderLabels(["Filename", "Size (KB)", "Created At"])
        self.table_backups.verticalHeader().setVisible(False)
        self.table_backups.verticalHeader().setDefaultSectionSize(38)
        self.table_backups.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_backups.setAlternatingRowColors(True)
        self.table_backups.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_backups.setShowGrid(False)

        header = self.table_backups.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        backup_layout.addWidget(self.table_backups)

        btn_restore = QPushButton(" RESTORE SELECTED BACKUP FILE")
        btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restore.setObjectName(ObjectNames.BTN_CANCEL)
        btn_restore.setIcon(IconHelper.get_icon("rotate-ccw", color=Colors.TEXT_MUTED, size=14))
        btn_restore.setIconSize(QSize(14, 14))
        btn_restore.clicked.connect(self._handle_restore_backup)
        attach_press_feedback(btn_restore)
        backup_layout.addWidget(btn_restore, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(backup_card)

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
            item_filename = QTableWidgetItem(b.get("filename", ""))
            
            size_bytes = b.get("size_bytes", 0) or 0
            size_kb = round(size_bytes / 1024, 1)
            item_size = QTableWidgetItem(f"{size_kb} KB")
            item_size.setForeground(QColor(Colors.ACCENT_GOLD))

            item_created = QTableWidgetItem(b.get("created_at", ""))

            item_filename.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_created.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table_backups.setItem(row, 0, item_filename)
            self.table_backups.setItem(row, 1, item_size)
            self.table_backups.setItem(row, 2, item_created)

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
            f"Are you sure you want to restore '{filename}'?\n\n"
            f"A safety recovery snapshot of the active database will be created automatically before overwriting.",
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