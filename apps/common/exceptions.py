"""
Custom exception handler for Django REST Framework.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.common.xlib.exceptions import (
    BaseAppException,
    ConflictException,
    InvalidCredentialsException,
    NotFoundException,
    PermissionException,
    ValidationException,
)

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.

    This handler wraps the default DRF exception handler to provide
    consistent error response formatting, mapping custom application
    exceptions to appropriate HTTP 4xx responses.
    """
    # 1. Handle our custom application exceptions
    if isinstance(exc, BaseAppException):
        if isinstance(exc, ValidationException):
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        elif isinstance(exc, NotFoundException):
            return Response(
                {"error": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )
        elif isinstance(exc, PermissionException):
            return Response(
                {"error": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        elif isinstance(exc, ConflictException):
            return Response(
                {"error": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        elif isinstance(exc, InvalidCredentialsException):
            return Response(
                {"error": str(exc)},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        else:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # 2. Handle built-in DRF exceptions
    response = exception_handler(exc, context)

    # If response is None, it's an unhandled server error
    if response is None:
        logger.exception("Unhandled server error occurred: %s", str(exc))
        from django.conf import settings

        if settings.DEBUG:
            return Response(
                {
                    "error": "Internal server error",
                    "detail": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "error": "Internal server error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
