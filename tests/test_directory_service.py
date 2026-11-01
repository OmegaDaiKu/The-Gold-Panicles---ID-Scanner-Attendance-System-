import pytest

from src.core.exceptions import DuplicateRecordError, ValidationError
from src.services.directory_service import DirectoryService


def test_directory_service_registers_staff_and_normalizes_name(db_manager):
    service = DirectoryService(db_manager)
    record = service.register_staff(
        student_id_no=" 261-00105 ",
        full_name="  Maria   Clara  ",
        designation="News Writer",
    )

    assert record["student_id_no"] == "261-00105"
    assert record["full_name"] == "Maria Clara"
    assert record["designation"] == "News Writer"
    assert record["is_active"] == 1


def test_directory_service_rejects_duplicate_student_id(db_manager):
    service = DirectoryService(db_manager)
    service.register_staff("261-00105", "First Staff", "News Writer")

    with pytest.raises(DuplicateRecordError):
        service.register_staff("261-00105", "Second Staff", "News Writer")


def test_directory_service_rejects_invalid_student_id(db_manager):
    service = DirectoryService(db_manager)

    with pytest.raises(ValidationError):
        service.register_staff("not-an-id", "Valid Name", "News Writer")


def test_directory_service_rejects_invalid_designation(db_manager):
    service = DirectoryService(db_manager)

    with pytest.raises(ValidationError):
        service.register_staff("261-00106", "Valid Name", "Made Up Role")
