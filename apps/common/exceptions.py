"""
Custom exception handler for Django REST Framework.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.

    This handler wraps the default DRF exception handler to provide
    consistent error response formatting.
    """
    response = exception_handler(exc, context)

    # If response is None, use default error handling
    if response is None:
        return Response(
            {
                "error": "Internal server error",
                "detail": str(exc),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response
