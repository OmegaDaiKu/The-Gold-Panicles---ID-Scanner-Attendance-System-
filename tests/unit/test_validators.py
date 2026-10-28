"""Unit tests for student ID format validation and name sanitization."""

import pytest

from src.core.exceptions import ValidationError
from src.utils.validators import (
    extract_student_id_from_payload,
    is_valid_student_id,
    validate_person_name,
    validate_student_id_format,
)


def test_validate_student_id_format_valid():
    """Verifies that valid CSU student IDs pass unchanged."""
    assert validate_student_id_format("261-00105") == "261-00105"
    assert validate_student_id_format("  201-12345  ") == "201-12345"


def test_validate_student_id_format_invalid():
    """Verifies that non-matching student IDs raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_student_id_format("26100105")  # Missing hyphen
        
    with pytest.raises(ValidationError):
        validate_student_id_format("ABC-00105")  # Non-numeric prefix
        
    with pytest.raises(ValidationError):
        validate_student_id_format("261-123")    # Insufficient trailing digits


def test_is_valid_student_id():
    """Verifies boolean student ID matcher."""
    assert is_valid_student_id("261-00105") is True
    assert is_valid_student_id("221-98765") is True
    assert is_valid_student_id("invalid-id") is False
    assert is_valid_student_id("") is False


def test_validate_person_name():
    """Verifies name string trimming and length checks."""
    assert validate_person_name("  John  Brian  Escol  ") == "John Brian Escol"
    
    with pytest.raises(ValidationError):
        validate_person_name("   ")
        
    with pytest.raises(ValidationError):
        validate_person_name("A")


def test_extract_student_id_from_payload():
    """Verifies extraction of student ID from direct and raw JSON/embedded payloads."""
    # Direct payload
    sid, raw = extract_student_id_from_payload("261-00105")
    assert sid == "261-00105"
    assert raw == "261-00105"

    # Embedded payload
    embedded = '{"student_no": "261-00105", "university": "CSU"}'
    sid_emb, _ = extract_student_id_from_payload(embedded)
    assert sid_emb == "261-00105"

    # Invalid payload
    sid_inv, raw_inv = extract_student_id_from_payload("UNRECOGNIZED_QR_DATA")
    assert sid_inv is None
    assert raw_inv == "UNRECOGNIZED_QR_DATA"