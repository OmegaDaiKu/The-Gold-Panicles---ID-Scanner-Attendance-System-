"""Audit service wrapper for recording immutable administrative action logs."""

from typing import Dict, List, Optional

from src.database.connection import DatabaseConnectionManager
from src.database.repositories.audit_repo import AuditRepository
from src.utils.time_utils import get_utc_now_iso


class AuditService:
    """Provides high-level audit logging operations."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager
        self.audit_repo = AuditRepository(db_manager)

    def log_action(
        self,
        admin_id: Optional[int],
        action_type: str,
        entity_type: str,
        entity_id: int,
        reason: str,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
    ) -> int:
        """Appends an entry to the audit log trail."""
        now_iso = get_utc_now_iso()
        return self.audit_repo.log(
            admin_id=admin_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            reason=reason,
            timestamp=now_iso,
            old_values=old_values,
            new_values=new_values,
        )

    def get_recent_logs(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Retrieves historical audit entries."""
        return self.audit_repo.list_logs(limit=limit, offset=offset)