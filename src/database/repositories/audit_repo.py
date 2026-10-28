"""Repository DAO for Audit logs append-only database operations."""

import json
from typing import Dict, List, Optional
from src.database.connection import DatabaseConnectionManager
from src.utils.time_utils import get_utc_now_iso


class AuditRepository:
    """Data access object for logging administrative audit events."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager

    def log_action(
        self,
        admin_id: Optional[int],
        action_type: str,
        entity_type: str,
        entity_id: int,
        reason: str,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        if not timestamp:
            timestamp = get_utc_now_iso()

        sql = """
            INSERT INTO audit_logs (admin_id, action_type, entity_type, entity_id, old_values_json, new_values_json, reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        old_json = json.dumps(old_values, default=str) if old_values is not None else None
        new_json = json.dumps(new_values, default=str) if new_values is not None else None

        with self.db.transaction() as conn:
            cursor = conn.execute(
                sql,
                (admin_id, action_type, entity_type, entity_id, old_json, new_json, reason, timestamp),
            )
            return cursor.lastrowid

    log = log_action

    def list_logs(self, limit: Optional[int] = 100, offset: int = 0) -> List[Dict]:
        sql = """
            SELECT a.*, u.username as admin_username
            FROM audit_logs a
            LEFT JOIN admin_users u ON a.admin_id = u.id
            ORDER BY a.id DESC
        """
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ? OFFSET ?;"
            params = (limit, offset)
        else:
            sql += ";"

        with self.db.transaction() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]