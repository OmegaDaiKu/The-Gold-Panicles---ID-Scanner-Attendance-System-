""""Directory management service for staff roster operations."""

import sqlite3
from typing import Dict, List, Optional
from src.core.constants import get_slot_limit
from src.database.connection import DatabaseConnectionManager
from src.database.repositories.staff_repo import StaffRepository
from src.core.exceptions import DesignationCapacityError, DuplicateRecordError, RecordNotFoundError
from src.utils.validators import sanitize_student_id, validate_designation, validate_person_name

_DEFAULT_REGISTRATION_DESIGNATION = "News Writer"


class DirectoryService:
    """Manages staff directory CRUD operations."""

    def __init__(self, db_manager: DatabaseConnectionManager):
        self.db = db_manager
        self.staff_repo = StaffRepository(db_manager)

    def register_staff(
        self,
        student_id_no: str,
        full_name: str,
        designation: Optional[str] = None,
        admin_id: Optional[int] = None,
        created_at: Optional[str] = None,
    ) -> Dict:
        """Registers a new staff member into the roster and records an audit entry."""
        if designation is None:
            designation = _DEFAULT_REGISTRATION_DESIGNATION

        clean_sid = sanitize_student_id(student_id_no)
        clean_name = validate_person_name(full_name)
        clean_desig = validate_designation(designation)

        try:
            staff_id = self.staff_repo.create(
                student_id_no=clean_sid,
                full_name=clean_name,
                designation=clean_desig,
                created_at=created_at,
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateRecordError(
                f"A staff member with ID '{clean_sid}' is already registered."
            ) from e

        record = self.staff_repo.get_by_id(staff_id)

        if admin_id is not None:
            from src.services.audit_service import AuditService
            AuditService(self.db).log_action(
                admin_id=admin_id,
                action_type="REGISTER_STAFF",
                entity_type="staff",
                entity_id=staff_id,
                reason=f"Registered new staff member {clean_name} ({clean_sid}) as {clean_desig}.",
            )

        return record

    def list_staff(self, active_only: bool = True) -> List[Dict]:
        """Lists staff members from the repository."""
        return self.staff_repo.list_all(active_only=active_only)

    def update_staff(
        self,
        staff_id: int,
        name: Optional[str] = None,
        full_name: Optional[str] = None,
        designation: Optional[str] = None,
        active: Optional[bool] = None,
        is_active: Optional[int] = None,
        admin_id: Optional[int] = None,
    ) -> Dict:
        """Updates staff details in repository and logs an audit trail entry."""
        old_record = self.staff_repo.get_by_id(staff_id)
        if not old_record:
            raise RecordNotFoundError(f"Staff member {staff_id} not found.")

        target_name = full_name if full_name is not None else name
        clean_name = validate_person_name(target_name) if target_name is not None else None
        clean_desig = validate_designation(designation) if designation is not None else None

        updated_record = self.staff_repo.update(
            staff_id,
            name=clean_name,
            full_name=clean_name,
            designation=clean_desig,
            active=active,
            is_active=is_active,
        )

        if admin_id is not None:
            from src.services.audit_service import AuditService
            changes = []
            if clean_name is not None:
                changes.append(f"name → '{clean_name}'")
            if clean_desig is not None:
                changes.append(f"designation → '{clean_desig}'")
            if active is not None or is_active is not None:
                changes.append("active status changed")
            change_summary = "; ".join(changes) if changes else "no field changes detected"

            AuditService(self.db).log_action(
                admin_id=admin_id,
                action_type="UPDATE_STAFF",
                entity_type="staff",
                entity_id=staff_id,
                reason=(
                    f"Updated staff record for {old_record['full_name']} "
                    f"({old_record['student_id_no']}): {change_summary}."
                ),
                old_values=old_record,
            )

        return updated_record

    def update_staff_info(
        self,
        staff_id: int,
        name: Optional[str] = None,
        full_name: Optional[str] = None,
        designation: Optional[str] = None,
        active: Optional[bool] = None,
        is_active: Optional[int] = None,
        admin_id: Optional[int] = None,
    ) -> Dict:
        """Alias for update_staff."""
        return self.update_staff(
            staff_id,
            name=name,
            full_name=full_name,
            designation=designation,
            active=active,
            is_active=is_active,
            admin_id=admin_id,
        )

    def set_staff_active_status(
        self,
        staff_id: int,
        is_active: int,
        admin_id: Optional[int] = None,
    ) -> Dict:
        """Activates or deactivates a staff record directly and logs an audit entry.

        FIXED THIS SESSION (confirmed audit finding H1): reactivating a staff
        member previously performed NO designation-slot-capacity check at all,
        unlike the create/edit path (which is gated by has_available_slot() in
        the UI layer). This allowed an admin to deactivate a full-designation
        holder, promote someone else into that now-open slot, and then
        reactivate the original holder -- silently exceeding the designation's
        intended headcount limit with no warning anywhere. Now mirrors the
        same has_available_slot() check used elsewhere, and raises
        DesignationCapacityError (a subclass of AppError, already caught by
        staff_mgmt.py's existing exception handler) if the designation is full.
        """
        staff = self.staff_repo.get_by_id(staff_id)
        if not staff:
            raise RecordNotFoundError(f"Staff member {staff_id} not found.")

        if is_active:
            designation = staff["designation"]
            if not self.staff_repo.has_available_slot(designation, exclude_pk=staff_id):
                limit = get_slot_limit(designation)
                raise DesignationCapacityError(
                    f"Cannot reactivate {staff['full_name']}: the designation "
                    f"'{designation}' already has all {limit} slot(s) filled by "
                    f"other active staff. Deactivate or reassign the current "
                    f"holder before reactivating this record."
                )

        updated_record = self.staff_repo.update(staff_id, is_active=is_active)

        if admin_id is not None:
            from src.services.audit_service import AuditService
            action_word = "Reactivated" if is_active else "Deactivated"
            AuditService(self.db).log_action(
                admin_id=admin_id,
                action_type="REACTIVATE_STAFF" if is_active else "DEACTIVATE_STAFF",
                entity_type="staff",
                entity_id=staff_id,
                reason=f"{action_word} staff member {staff['full_name']} ({staff['student_id_no']}).",
                old_values=staff,
            )

        return updated_record

    def delete_staff(self, staff_id: int, admin_id: Optional[int] = None) -> Dict:
        """Deletes a staff record permanently if safe, or soft-deactivates it when history exists."""
        staff = self.staff_repo.get_by_id(staff_id)
        if not staff:
            raise RecordNotFoundError(f"Staff member {staff_id} not found.")

        try:
            self.staff_repo.delete(staff_id)
            status = "deleted"
            action_type = "DELETE_STAFF"
            reason = (
                f"Permanently deleted staff member {staff['full_name']} "
                f"({staff['student_id_no']})."
            )
        except sqlite3.IntegrityError:
            self.staff_repo.update(staff_id, is_active=0)
            status = "deactivated"
            action_type = "DEACTIVATE_STAFF"
            reason = (
                f"Staff member {staff['full_name']} ({staff['student_id_no']}) has existing "
                f"attendance history and cannot be permanently deleted; deactivated instead."
            )

        if admin_id is not None:
            from src.services.audit_service import AuditService
            AuditService(self.db).log_action(
                admin_id=admin_id,
                action_type=action_type,
                entity_type="staff",
                entity_id=staff_id,
                reason=reason,
                old_values=staff,
            )

        return {"status": status, "staff_id": staff_id}