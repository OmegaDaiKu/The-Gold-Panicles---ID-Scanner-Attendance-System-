"""Authentication and admin account service layer using Argon2id password hashing."""

import argon2
from typing import Dict, Optional

from src.core.exceptions import AuthenticationError, RecordNotFoundError, ValidationError
from src.database.connection import DatabaseConnectionManager
from src.database.repositories.admin_repo import AdminRepository
from src.database.repositories.audit_repo import AuditRepository
from src.utils.time_utils import get_utc_now_iso


class AuthService:
    """Manages administrator authentication, password hashing, and account creation."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager
        self.admin_repo = AdminRepository(db_manager)
        self.audit_repo = AuditRepository(db_manager)
        self.ph = argon2.PasswordHasher()

    def is_setup_required(self) -> bool:
        """Checks whether any admin account exists in the database."""
        return self.admin_repo.count_admins() == 0

    def ensure_default_admin_exists(self) -> Dict:
        """Guarantees that a default 'admin' account exists with known credentials."""
        existing = self.admin_repo.get_by_username("admin")
        if existing:
            if existing["is_active"] == 0:
                now_iso = get_utc_now_iso()
                with self.db.transaction() as conn:
                    conn.execute(
                        "UPDATE admin_users SET is_active = 1, updated_at = ? WHERE id = ?;",
                        (now_iso, existing["id"]),
                    )
                existing = self.admin_repo.get_by_id(existing["id"])
            return existing  # type: ignore

        now_iso = get_utc_now_iso()
        pwd_hash = self.ph.hash("AdminPassword123!")
        admin_id = self.admin_repo.create_admin("admin", pwd_hash, "MASTER_ADMIN", now_iso)
        return self.admin_repo.get_by_id(admin_id)  # type: ignore

    def create_admin(
        self,
        creator_admin_id: Optional[int],
        username: str,
        plain_password: str,
        role: str = "MASTER_ADMIN",
    ) -> Dict:
        """Registers a new administrator user with Argon2id hashed password."""
        clean_user = username.strip().lower()
        if not clean_user or len(clean_user) < 3:
            raise ValidationError("Username must be at least 3 characters long.")

        if not plain_password or len(plain_password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")

        existing = self.admin_repo.get_by_username(clean_user)
        if existing:
            raise ValidationError(f"Username '{clean_user}' is already taken.")

        pwd_hash = self.ph.hash(plain_password)
        now_iso = get_utc_now_iso()

        admin_id = self.admin_repo.create_admin(clean_user, pwd_hash, role, now_iso)
        record = self.admin_repo.get_by_id(admin_id)

        if not record:
            raise RecordNotFoundError("Failed to retrieve created admin user.")

        if creator_admin_id:
            self.audit_repo.log_action(
                admin_id=creator_admin_id,
                action_type="CREATE_ADMIN",
                entity_type="admin_users",
                entity_id=admin_id,
                reason=f"Created new admin user: {clean_user}",
                old_values=None,
                new_values={"username": clean_user, "role": role},
                timestamp=now_iso,
            )

        return record

    def authenticate(self, username: str, plain_password: str) -> Dict:
        """Authenticates admin credentials against stored Argon2id hash."""
        clean_user = username.strip().lower()
        account = self.admin_repo.get_by_username(clean_user)

        if not account or account["is_active"] == 0:
            raise AuthenticationError("Invalid username or password.")

        try:
            self.ph.verify(account["password_hash"], plain_password)
        except (
            argon2.exceptions.VerifyMismatchError,
            argon2.exceptions.VerificationError,
            argon2.exceptions.InvalidHashError,
        ):
            raise AuthenticationError("Invalid username or password.")

        try:
            needs_rehash = self.ph.check_needs_rehash(account["password_hash"])
        except argon2.exceptions.InvalidHashError:
            needs_rehash = True

        if needs_rehash:
            new_hash = self.ph.hash(plain_password)
            now_iso = get_utc_now_iso()
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE admin_users SET password_hash = ?, updated_at = ? WHERE id = ?;",
                    (new_hash, now_iso, account["id"]),
                )

        now_iso = get_utc_now_iso()
        self.admin_repo.update_last_login(account["id"], now_iso)

        fresh_account = self.admin_repo.get_by_id(account["id"])
        return fresh_account if fresh_account else account