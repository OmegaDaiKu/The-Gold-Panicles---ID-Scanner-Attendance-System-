import pytest

from src.core.constants import OFFICIAL_DESIGNATIONS
from src.core.exceptions import ValidationError
from src.utils.validators import (
    extract_student_id_from_payload,
    is_valid_student_id,
    sanitize_student_id,
    validate_designation,
    validate_person_name,
)


@pytest.mark.parametrize("student_id", ["261-00105", "001-00001", "999-99999"])
def test_valid_student_id_formats_are_accepted(student_id):
    assert is_valid_student_id(student_id)
    assert sanitize_student_id(student_id) == student_id


@pytest.mark.parametrize(
    "student_id",
    ["", "26100105", "26-00105", "261-0105", "261-001050", "abc-defgh", "261 00105"],
)
def test_invalid_student_id_formats_are_rejected(student_id):
    assert not is_valid_student_id(student_id)
    with pytest.raises(ValidationError):
        sanitize_student_id(student_id)


def test_student_id_normalization_strips_outer_whitespace():
    assert sanitize_student_id("  261-00105  ") == "261-00105"


def test_qr_payload_extracts_student_id_from_surrounding_text():
    extracted, payload = extract_student_id_from_payload("CSU|STUDENT: 261-00105|END")
    assert extracted == "261-00105"
    assert payload == "CSU|STUDENT: 261-00105|END"


def test_qr_payload_returns_none_when_no_student_id_is_present():
    extracted, payload = extract_student_id_from_payload("NOT A VALID QR PAYLOAD")
    assert extracted is None
    assert payload == "NOT A VALID QR PAYLOAD"


def test_person_name_collapses_repeated_whitespace():
    assert validate_person_name("  Juan   Dela   Cruz ") == "Juan Dela Cruz"


@pytest.mark.parametrize("name", ["", " ", "A", None])
def test_person_name_rejects_empty_or_too_short_values(name):
    with pytest.raises(ValidationError):
        validate_person_name(name)


def test_official_designation_is_accepted():
    designation = OFFICIAL_DESIGNATIONS[0]
    assert validate_designation(designation) == designation


def test_unrecognized_designation_is_rejected():
    with pytest.raises(ValidationError):
        validate_designation("Chief Supreme Editor")
