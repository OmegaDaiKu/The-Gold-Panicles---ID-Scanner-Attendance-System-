"""Basic import smoke tests: catch missing modules and import-time errors."""

def test_core_application_modules_import():
    import main
    import src.core.constants
    import src.core.exceptions
    import src.database.connection
    import src.database.schema
    import src.database.repositories.admin_repo
    import src.database.repositories.attendance_repo
    import src.database.repositories.audit_repo
    import src.database.repositories.staff_repo
    import src.database.repositories.visitor_repo
    import src.services.attendance_service
    import src.services.auth_service
    import src.services.backup_service
    import src.services.directory_service
    import src.services.overdue_service
    import src.services.sync_service
    import src.utils.font_loader
    import src.utils.icon_helper
    import src.utils.time_utils
    import src.utils.validators

    assert main is not None
