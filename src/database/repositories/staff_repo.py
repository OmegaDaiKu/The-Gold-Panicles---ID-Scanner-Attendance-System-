""""Repository for staff roster CRUD operations with dynamic schema detection."""

import sqlite3
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from src.core.constants import OFFICIAL_DESIGNATIONS, get_slot_limit
from src.core.exceptions import DesignationCapacityError

_FALLBACK_DESIGNATION = "News Writer"


class StaffRepository:
    def __init__(self, db_connection: Any):
        self.conn = db_connection
        self._col_map_cache: Optional[Dict[str, str]] = None

    def _get_connection(self) -> sqlite3.Connection:
        if hasattr(self.conn, 'get_connection'):
            return self.conn.get_connection()
        if hasattr(self.conn, 'conn'):
            return self.conn.conn
        return self.conn

    @contextmanager
    def _db_scope(self):
        """Yields an active database connection, routing through DatabaseConnectionManager.transaction()
        when available to participate in reader-writer locking during database hot backups/restores."""
        if hasattr(self.conn, "transaction"):
            with self.conn.transaction() as conn:
                yield conn
        else:
            conn = self._get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @contextmanager
    def _capacity_checked_write(self):
        """Wraps a capacity check and write in an immediate transaction context."""
        if hasattr(self.conn, "transaction"):
            with self.conn.transaction() as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    pass
                yield conn
        else:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:
                pass
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _get_column_map(self) -> Dict[str, str]:
        if self._col_map_cache is not None:
            return self._col_map_cache

        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(staff)")
            cols = [row[1] for row in cursor.fetchall()]

            col_map: Dict[str, str] = {}

            col_map['pk'] = 'id' if 'id' in cols else (cols[0] if cols else 'id')

            for candidate in ['student_id_no', 'student_id', 'staff_id']:
                if candidate in cols:
                    col_map['student_id_no'] = candidate
                    break
            if 'student_id_no' not in col_map:
                col_map['student_id_no'] = col_map['pk']

            for candidate in ['id', 'staff_id', 'student_id']:
                if candidate in cols:
                    col_map['id'] = candidate
                    break
            if 'id' not in col_map and cols:
                col_map['id'] = cols[0]

            for candidate in ['name', 'full_name', 'staff_name']:
                if candidate in cols:
                    col_map['name'] = candidate
                    break

            for candidate in ['designation', 'primary_designation', 'role']:
                if candidate in cols:
                    col_map['designation'] = candidate
                    break

            for candidate in ['is_active', 'active', 'status']:
                if candidate in cols:
                    col_map['active'] = candidate
                    break

            for candidate in ['created_at', 'timestamp', 'date_created']:
                if candidate in cols:
                    col_map['created_at'] = candidate
                    break

            for candidate in ['updated_at', 'modified_at', 'last_modified']:
                if candidate in cols:
                    col_map['updated_at'] = candidate
                    break

            self._col_map_cache = col_map
            return col_map

    def _get_column_types(self) -> Dict[str, str]:
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(staff)")
            return {row[1]: (row[2] or "TEXT").upper() for row in cursor.fetchall()}

    def _coerce_timestamp(self, value: Optional[str], col_type: str) -> Any:
        if value is None:
            return None
        if col_type in ("INTEGER", "INT"):
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return int(dt.timestamp())
            except (ValueError, AttributeError):
                return value
        return value

    def validate_designation(self, designation: str) -> bool:
        return designation in OFFICIAL_DESIGNATIONS

    def count_active_by_designation(self, designation: str) -> int:
        col_map = self._get_column_map()
        desig_col = col_map.get('designation', 'designation')
        active_col = col_map.get('active', 'is_active')

        with self._db_scope() as conn:
            cursor = conn.cursor()
            if active_col in col_map.values():
                cursor.execute(
                    f"SELECT COUNT(*) FROM staff WHERE {desig_col} = ? AND {active_col} = 1",
                    (designation,),
                )
            else:
                cursor.execute(
                    f"SELECT COUNT(*) FROM staff WHERE {desig_col} = ?",
                    (designation,),
                )
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_active_designation_counts(self) -> Dict[str, int]:
        col_map = self._get_column_map()
        desig_col = col_map.get('designation', 'designation')
        active_col = col_map.get('active', 'is_active')

        with self._db_scope() as conn:
            cursor = conn.cursor()
            if active_col in col_map.values():
                cursor.execute(
                    f"SELECT {desig_col}, COUNT(*) FROM staff WHERE {active_col} = 1 "
                    f"GROUP BY {desig_col}"
                )
            else:
                cursor.execute(f"SELECT {desig_col}, COUNT(*) FROM staff GROUP BY {desig_col}")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def has_available_slot(self, designation: str, exclude_pk: Optional[int] = None) -> bool:
        limit = get_slot_limit(designation)
        if limit is None:
            return True

        col_map = self._get_column_map()
        desig_col = col_map.get('designation', 'designation')
        active_col = col_map.get('active', 'is_active')
        pk_col = col_map.get('pk', 'id')

        with self._db_scope() as conn:
            cursor = conn.cursor()
            if active_col in col_map.values():
                query = f"SELECT COUNT(*) FROM staff WHERE {desig_col} = ? AND {active_col} = 1"
            else:
                query = f"SELECT COUNT(*) FROM staff WHERE {desig_col} = ?"
            params: list = [designation]

            if exclude_pk is not None:
                query += f" AND {pk_col} != ?"
                params.append(exclude_pk)

            cursor.execute(query, params)
            row = cursor.fetchone()
            current_count = row[0] if row else 0
            return current_count < limit

    def add_staff(self, staff_id: str, name: str, designation: str) -> bool:
        if not self.validate_designation(designation):
            raise ValueError(
                f"Invalid designation: {designation}. Must be one of OFFICIAL_DESIGNATIONS."
            )

        col_map = self._get_column_map()
        id_col = col_map.get('id', 'id')
        name_col = col_map.get('name', 'name')
        desig_col = col_map.get('designation', 'designation')
        active_col = col_map.get('active', 'is_active')

        query = (
            f"INSERT INTO staff ({id_col}, {name_col}, {desig_col}, {active_col}) "
            f"VALUES (?, ?, ?, 1)"
        )
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (staff_id, name, designation))
            return cursor.rowcount > 0

    def create(
        self,
        staff_id: Optional[str] = None,
        full_name: Optional[str] = None,
        designation: Optional[str] = None,
        created_at: Optional[str] = None,
        **kwargs,
    ) -> int:
        sid = (
            staff_id
            or kwargs.get("student_id_no")
            or kwargs.get("staff_id")
            or kwargs.get("id")
            or kwargs.get("student_id")
        )
        name = full_name or kwargs.get("full_name") or kwargs.get("name")
        desig = (
            designation
            or kwargs.get("primary_designation")
            or kwargs.get("designation")
            or _FALLBACK_DESIGNATION
        )

        if desig not in OFFICIAL_DESIGNATIONS:
            if (
                isinstance(desig, str)
                and re.match(r'\d{4}-\d{2}-\d{2}', desig)
                and created_at is None
            ):
                created_at = desig
                desig = _FALLBACK_DESIGNATION
            else:
                raise ValueError(
                    f"Invalid designation: {desig}. Must be one of OFFICIAL_DESIGNATIONS."
                )

        if not sid:
            raise ValueError("staff_id is required and cannot be None.")

        col_map = self._get_column_map()
        col_types = self._get_column_types()

        sid_col = col_map.get('student_id_no', 'student_id_no')
        name_col = col_map.get('name', 'full_name')
        desig_col = col_map.get('designation', 'designation')
        active_col = col_map.get('active', 'is_active')
        created_col = col_map.get('created_at', 'created_at')

        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()

        created_at = self._coerce_timestamp(
            created_at, col_types.get(created_col, "TEXT")
        )

        with self._capacity_checked_write() as conn:
            if not self.has_available_slot(desig):
                limit = get_slot_limit(desig)
                raise DesignationCapacityError(
                    f"Cannot register staff with designation '{desig}': all {limit} slot(s) "
                    f"are currently filled by active staff. Deactivate or reassign an existing "
                    f"holder first."
                )

            cursor = conn.cursor()
            if created_col in col_map.values():
                query = (
                    f"INSERT INTO staff ({sid_col}, {name_col}, {desig_col}, "
                    f"{active_col}, {created_col}) VALUES (?, ?, ?, 1, ?)"
                )
                cursor.execute(query, (sid, name, desig, created_at))
            else:
                query = (
                    f"INSERT INTO staff ({sid_col}, {name_col}, {desig_col}, "
                    f"{active_col}) VALUES (?, ?, ?, 1)"
                )
                cursor.execute(query, (sid, name, desig))

            new_id = cursor.lastrowid

        return new_id

    def get_by_id(self, row_id: int) -> Optional[Dict[str, Any]]:
        col_map = self._get_column_map()
        pk_col = col_map.get('pk', 'id')

        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM staff WHERE {pk_col} = ?", (row_id,))
            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            record = dict(zip(columns, row))
            return self._row_to_dict(record, col_map)

    def get_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        col_map = self._get_column_map()
        sid_col = col_map.get('student_id_no', 'student_id_no')

        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM staff WHERE {sid_col} = ?", (student_id,))
            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            record = dict(zip(columns, row))
            return self._row_to_dict(record, col_map)

    def _row_to_dict(self, record: Dict[str, Any], col_map: Dict[str, str]) -> Dict[str, Any]:
        pk_col = col_map.get('pk', 'id')
        sid_col = col_map.get('student_id_no', pk_col)
        name_col = col_map.get('name', 'full_name')
        desig_col = col_map.get('designation', 'designation')
        active_col = col_map.get('active', 'is_active')
        created_col = col_map.get('created_at', 'created_at')
        updated_col = col_map.get('updated_at')

        return {
            "id": record.get(pk_col),
            "staff_id": record.get(sid_col),
            "student_id_no": record.get(sid_col),
            "student_id": record.get(sid_col),
            "full_name": record.get(name_col),
            "name": record.get(name_col),
            "designation": record.get(desig_col),
            "primary_designation": record.get(desig_col),
            "is_active": bool(record.get(active_col, True)),
            "created_at": record.get(created_col),
            "updated_at": record.get(updated_col) if updated_col else None,
        }

    def update(self, staff_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        col_map = self._get_column_map()
        col_types = self._get_column_types()
        pk_col = col_map.get('pk', 'id')

        sets: list = []
        params: list = []

        name = kwargs.get('full_name') if kwargs.get('full_name') is not None else kwargs.get('name')
        if name is not None:
            sets.append(f"{col_map.get('name', 'full_name')} = ?")
            params.append(name)

        desig = kwargs.get('designation')
        desig_changing = False
        current_record: Optional[Dict[str, Any]] = None
        if desig is not None:
            current_record = self.get_by_id(staff_id)
            current_desig = current_record.get('designation') if current_record else None
            desig_changing = desig != current_desig

            sets.append(f"{col_map.get('designation', 'designation')} = ?")
            params.append(desig)

        active = (
            kwargs.get('is_active')
            if kwargs.get('is_active') is not None
            else kwargs.get('active')
        )
        if active is not None:
            sets.append(f"{col_map.get('active', 'is_active')} = ?")
            params.append(int(active))

        if not sets:
            return self.get_by_id(staff_id)

        updated_col = col_map.get('updated_at')
        if updated_col:
            now_val = datetime.now(timezone.utc).isoformat()
            now_val = self._coerce_timestamp(now_val, col_types.get(updated_col, "TEXT"))
            sets.append(f"{updated_col} = ?")
            params.append(now_val)

        params.append(staff_id)

        # FIXED THIS SESSION (confirmed audit finding H1, closing a gap left
        # by an earlier DirectoryService.set_staff_active_status() fix):
        # previously ONLY desig_changing triggered the atomic capacity check
        # below. Reactivating a staff member (active: 0 -> 1) WITHOUT also
        # changing their designation performed no capacity check at all at
        # this layer, which is the one place that can enforce it atomically
        # inside the same locked transaction as the write itself. A
        # service-layer pre-check alone cannot fully close this race, since
        # it runs as a separate, non-atomic transaction before this one.
        # Now: any write that results in the record being active (whether
        # via a designation change, a reactivation, or both at once) is
        # capacity-checked here, atomically, against whichever designation
        # the record will hold once this update commits.
        activating = active is not None and int(active) == 1
        capacity_check_designation = None
        if desig_changing:
            capacity_check_designation = desig
        elif activating:
            if current_record is None:
                current_record = self.get_by_id(staff_id)
            capacity_check_designation = current_record.get('designation') if current_record else None

        with self._capacity_checked_write() as conn:
            if capacity_check_designation and not self.has_available_slot(
                capacity_check_designation, exclude_pk=staff_id
            ):
                limit = get_slot_limit(capacity_check_designation)
                raise DesignationCapacityError(
                    f"Cannot assign designation '{capacity_check_designation}': all {limit} "
                    f"slot(s) are currently filled by active staff. Deactivate or reassign "
                    f"an existing holder first."
                )

            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE staff SET {', '.join(sets)} WHERE {pk_col} = ?", params
            )

        return self.get_by_id(staff_id)

    def delete(self, staff_id: int) -> bool:
        pk_col = self._get_column_map().get('pk', 'id')
        with self._db_scope() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM staff WHERE {pk_col} = ?", (staff_id,))
            return cursor.rowcount > 0

    def list_all(self, active_only: bool = False) -> List[Dict[str, Any]]:
        col_map = self._get_column_map()
        pk_col = col_map.get('pk', 'id')
        sid_col = col_map.get('student_id_no', pk_col)
        name_col = col_map.get('name', 'full_name')
        desig_col = col_map.get('designation', 'designation')
        active_col = col_map.get('active', 'is_active')
        created_col = col_map.get('created_at', 'created_at')

        with self._db_scope() as conn:
            cursor = conn.cursor()

            raw_cols = [pk_col, sid_col, name_col, desig_col]
            if active_col in col_map.values():
                raw_cols.append(active_col)
            if created_col in col_map.values():
                raw_cols.append(created_col)

            seen: set = set()
            cols_to_select: list = []
            for c in raw_cols:
                if c not in seen:
                    seen.add(c)
                    cols_to_select.append(c)

            cols_sql = ", ".join(cols_to_select)

            if active_only and active_col in col_map.values():
                cursor.execute(
                    f"SELECT {cols_sql} FROM staff WHERE {active_col} = 1 "
                    f"ORDER BY {name_col} ASC"
                )
            else:
                cursor.execute(
                    f"SELECT {cols_sql} FROM staff ORDER BY {name_col} ASC"
                )

            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]

            staff_list: list = []
            for row in rows:
                d = dict(zip(col_names, row))
                is_active_val = (
                    bool(d[active_col]) if active_col in d and d[active_col] is not None else True
                )
                staff_list.append({
                    "staff_id": d.get(sid_col),
                    "id": d.get(pk_col),
                    "student_id": d.get(sid_col),
                    "student_id_no": d.get(sid_col),
                    "full_name": d.get(name_col),
                    "name": d.get(name_col),
                    "primary_designation": d.get(desig_col),
                    "designation": d.get(desig_col),
                    "is_active": is_active_val,
                    "created_at": d.get(created_col),
                })
            return staff_list

    def delete_staff(self, staff_id: str) -> Dict[str, Any]:
        col_map = self._get_column_map()
        id_col = col_map.get('id', 'id')
        active_col = col_map.get('active', 'is_active')

        with self._db_scope() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='attendance_sessions'"
            )
            table_exists = cursor.fetchone() is not None

            session_count = 0
            if table_exists:
                cursor.execute("PRAGMA table_info(attendance_sessions)")
                session_cols = [r[1] for r in cursor.fetchall()]
                fk_col = None
                for candidate in ['staff_id', 'student_id', 'student_id_no']:
                    if candidate in session_cols:
                        fk_col = candidate
                        break
                if fk_col:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM attendance_sessions WHERE {fk_col} = ?",
                        (staff_id,),
                    )
                    session_count = cursor.fetchone()[0]

            if session_count > 0:
                if active_col in col_map.values():
                    cursor.execute(
                        f"UPDATE staff SET {active_col} = 0 WHERE {id_col} = ?",
                        (staff_id,),
                    )
                    return {
                        "status": "deactivated",
                        "message": (
                            f"Staff ID '{staff_id}' has {session_count} "
                            f"historical session logs. Account set to inactive."
                        ),
                    }
                return {
                    "status": "error",
                    "message": (
                        f"Staff ID '{staff_id}' has {session_count} session logs "
                        f"but no active column exists for soft-delete."
                    ),
                }

            cursor.execute(f"DELETE FROM staff WHERE {id_col} = ?", (staff_id,))
            return {
                "status": "deleted",
                "message": f"Staff ID '{staff_id}' had no session history and was permanently removed.",
            }