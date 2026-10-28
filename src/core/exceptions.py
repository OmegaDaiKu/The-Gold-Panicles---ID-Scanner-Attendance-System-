"""Custom domain exceptions for business logic and validation errors."""


class AppError(Exception):
    """Base exception class for application errors."""

    pass


# Base exception alias for UI view imports
TGPError = AppError


class ValidationError(AppError):
    """Raised when input parameters fail domain validation rules."""

    pass


class RecordNotFoundError(AppError):
    """Raised when a requested database record does not exist."""

    pass


class DuplicateRecordError(AppError):
    """Raised when attempting to create a record that violates uniqueness constraints."""

    pass


class InvalidStateError(AppError):
    """Raised when an operation is invalid for the record's current state."""

    pass


class AuthenticationError(AppError):
    """Raised when admin credentials or authorization checks fail."""

    pass


class DatabaseError(AppError):
    """Raised when database operations encounter errors."""

    pass


class DesignationCapacityError(AppError):
    """Raised when a designation has reached its maximum allowed active headcount."""

    pass