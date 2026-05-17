"""
Custom exceptions for the application.
"""


class BaseAppException(Exception):
    """Base exception for the application."""

    pass


class ValidationException(BaseAppException):
    """Raised when data validation fails."""

    pass


class NotFoundException(BaseAppException):
    """Raised when a requested resource is not found."""

    pass


class PermissionException(BaseAppException):
    """Raised when user lacks required permissions."""

    pass


class ConflictException(BaseAppException):
    """Raised when there is a data conflict."""

    pass
