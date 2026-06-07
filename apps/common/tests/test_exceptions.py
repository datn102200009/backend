import pytest
from rest_framework import status
from rest_framework.response import Response

from apps.common.exceptions import custom_exception_handler
from apps.common.xlib.exceptions import (
    BaseAppException,
    ConflictException,
    NotFoundException,
    PermissionException,
    ValidationException,
)


class TestCustomExceptionHandler:
    """Test suite cho custom_exception_handler."""

    def test_validation_exception_returns_400(self):
        exc = ValidationException("Dữ liệu không hợp lệ")
        response = custom_exception_handler(exc, {})
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {"error": "Dữ liệu không hợp lệ"}

    def test_not_found_exception_returns_404(self):
        exc = NotFoundException("Không tìm thấy tài nguyên")
        response = custom_exception_handler(exc, {})
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {"error": "Không tìm thấy tài nguyên"}

    def test_permission_exception_returns_403(self):
        exc = PermissionException("Không có quyền truy cập")
        response = custom_exception_handler(exc, {})
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data == {"error": "Không có quyền truy cập"}

    def test_conflict_exception_returns_409(self):
        exc = ConflictException("Xung đột dữ liệu xảy ra")
        response = custom_exception_handler(exc, {})
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data == {"error": "Xung đột dữ liệu xảy ra"}

    def test_generic_base_app_exception_returns_400(self):
        class SubAppException(BaseAppException):
            pass

        exc = SubAppException("Lỗi ứng dụng chung")
        response = custom_exception_handler(exc, {})
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {"error": "Lỗi ứng dụng chung"}

    def test_unhandled_exception_returns_500(self):
        from django.conf import settings

        exc = RuntimeError("Lỗi nghiêm trọng hệ thống")
        response = custom_exception_handler(exc, {})
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["error"] == "Internal server error"
        if settings.DEBUG:
            assert "Lỗi nghiêm trọng hệ thống" in response.data["detail"]
        else:
            assert "detail" not in response.data
