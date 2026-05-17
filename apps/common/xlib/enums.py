"""
Common enumerations used across the application.
"""

from enum import Enum


class BaseEnum(Enum):
    """Base enum class with common utility methods."""

    @classmethod
    def choices(cls):
        """Return choices for Django model fields."""
        return [(item.value, item.name) for item in cls]

    @classmethod
    def values(cls):
        """Return all values."""
        return [item.value for item in cls]

    @classmethod
    def names(cls):
        """Return all names."""
        return [item.name for item in cls]
