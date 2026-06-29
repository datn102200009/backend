from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.common.xlib.exceptions import PermissionException, ValidationException
from apps.hrm.services import leave_request_approve
from apps.hrm.tests.factories import EmployeeFactory, LeaveRequestFactory
from apps.inventory.tests.factories import UserFactory


@pytest.fixture
def mock_check_permission():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as mock:
        mock.return_value = True
        yield mock


@pytest.mark.django_db
class TestHrmPermissionAndBypass:

    def test_leave_request_approve_fails_if_approver_does_not_exist(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP9988")
        leave_request = LeaveRequestFactory(employee=employee, status="pending")

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            leave_request_approve(
                leave_request_id=leave_request.id,
                approved_by_user_id="00000000-0000-0000-0000-000000000000",  # Random non-existent UUID
            )
        assert "Người phê duyệt không tồn tại" in str(exc_info.value)

    def test_leave_request_approve_fails_if_no_permission(self, mock_check_permission):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP9987")
        leave_request = LeaveRequestFactory(employee=employee, status="pending")
        approver = UserFactory(username="no_permission_approver")

        # Mock check_permission raise PermissionException
        mock_check_permission.side_effect = PermissionException("Người dùng không có quyền: hrm.change_leaverequest")

        # Act & Assert
        with pytest.raises(PermissionException) as exc_info:
            leave_request_approve(
                leave_request_id=leave_request.id,
                approved_by_user_id=str(approver.id),
            )
        assert "không có quyền: hrm.change_leaverequest" in str(exc_info.value)
