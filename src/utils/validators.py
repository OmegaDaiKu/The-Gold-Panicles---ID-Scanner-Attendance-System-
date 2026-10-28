"""Input sanitization and validation utilities for student IDs, names, and staff designations."""

import re
from typing import Optional, Tuple
from src.core.constants import OFFICIAL_DESIGNATIONS
from src.core.exceptions import ValidationError


STUDENT_ID_REGEX = re.compile(r"^\d{3}-\d{5}$")
PAYLOAD_STUDENT_ID_REGEX = re.compile(r"\b(\d{3}-\d{5})\b")


def is_valid_student_id(student_id: str) -> bool:
    """Checks whether a string matches the standard Student ID format XXX-XXXXX."""
    if not student_id:
        return False
    return bool(STUDENT_ID_REGEX.match(student_id.strip()))


def sanitize_student_id(raw_id: str) -> str:
    """Sanitizes and normalizes Student ID string while preserving leading zeroes."""
    if not raw_id:
        raise ValidationError("Student ID Number cannot be empty.")

    clean_id = raw_id.strip()

    if not STUDENT_ID_REGEX.match(clean_id):
        raise ValidationError(f"Invalid Student ID format '{clean_id}'. Expected format: XXX-XXXXX (e.g., 261-00105).")

    return clean_id


validate_student_id_format = sanitize_student_id


def extract_student_id_from_payload(payload: str) -> Tuple[Optional[str], str]:
    """Extracts student ID number matching XXX-XXXXX format from raw QR code payload."""
    if not payload:
        return None, ""

    clean_payload = payload.strip()
    match = PAYLOAD_STUDENT_ID_REGEX.search(clean_payload)
    if match:
        extracted_id = match.group(1)
    else:
        try:
            extracted_id = sanitize_student_id(clean_payload)
        except ValidationError:
            extracted_id = None

    return extracted_id, clean_payload


def validate_person_name(name: str) -> str:
    """Validates and sanitizes a staff or guest visitor name, collapsing extra internal whitespace."""
    if not name or not name.strip():
        raise ValidationError("Name cannot be empty.")

    clean_name = " ".join(name.strip().split())
    if len(clean_name) < 2:
        raise ValidationError("Name must be at least 2 characters long.")

    return clean_name


def validate_designation(designation: str) -> str:
    """Validates that a designation belongs to the official publication roles."""
    clean_desig = designation.strip()

    if clean_desig not in OFFICIAL_DESIGNATIONS:
        raise ValidationError(
            f"Invalid designation '{clean_desig}'. Must be one of the official publication roles."
        )

    return clean_desig