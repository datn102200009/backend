"""
Custom validators for model fields and data validation.
"""

from django.core.exceptions import ValidationError


def validate_phone_number(value):
    """Validate Vietnamese phone number format."""
    if not value.startswith("0") or len(value) != 10:
        raise ValidationError("Phone number must start with 0 and have 10 digits.")


def validate_positive(value):
    """Validate that value is positive."""
    if value <= 0:
        raise ValidationError("Value must be positive.")
