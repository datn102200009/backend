from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.common.xlib.exceptions import ValidationException
from apps.finance.services import payroll_approve_slip, payroll_bulk_approve
from apps.hrm.tests.factories import EmployeeFactory, SalarySlipFactory


@pytest.fixture(autouse=True)
def mock_check_permission():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as m:
        m.return_value = True
        yield m


@pytest.mark.django_db
class TestPayrollApproveCurrentPeriodBlock:

    @pytest.fixture
    def user(self, db):
        from apps.accounts.models import User

        return User.objects.create(username="test_finance_user")

    def test_approve_blocked_for_current_period(self, user):
        """Kỳ hiện tại: phê duyệt bị chặn."""
        current_period = "2026-06"
        employee = EmployeeFactory()
        slip = SalarySlipFactory(
            employee=employee,
            salary_period=current_period,
            status="pending_finance_review",
        )

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.finance.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            with pytest.raises(ValidationException, match="tháng hiện tại"):
                payroll_approve_slip(salary_slip_id=str(slip.id), user=user)

    def test_approve_allowed_for_previous_period(self, user):
        """Kỳ tháng trước: phê duyệt được phép."""
        previous_period = "2026-05"
        employee = EmployeeFactory()
        slip = SalarySlipFactory(
            employee=employee,
            salary_period=previous_period,
            status="pending_finance_review",
        )

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.finance.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            result = payroll_approve_slip(salary_slip_id=str(slip.id), user=user)
            assert result.status == "approved"

    def test_approve_allowed_for_final_slip_current_period(self, user):
        """Final slip kỳ hiện tại: phê duyệt được phép."""
        employee = EmployeeFactory()
        slip = SalarySlipFactory(
            employee=employee,
            name=f"FINAL-SALARY-{employee.employee_id}-2026-06",
            salary_period="2026-06",
            status="pending_finance_review",
        )

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.finance.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            result = payroll_approve_slip(salary_slip_id=str(slip.id), user=user)
            assert result.status == "approved"

    def test_bulk_approve_blocked_for_current_period(self, user):
        """Bulk approve cũng bị chặn cho kỳ hiện tại."""
        employees = [EmployeeFactory() for _ in range(3)]
        for emp in employees:
            SalarySlipFactory(employee=emp, salary_period="2026-06", status="pending_finance_review")

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.finance.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            with pytest.raises(ValidationException, match="tháng hiện tại"):
                payroll_bulk_approve(salary_period="2026-06", creator=user)

    def test_bulk_approve_allowed_for_previous_period(self, user):
        """Bulk approve hoạt động bình thường với kỳ tháng trước."""
        employees = [EmployeeFactory() for _ in range(3)]
        for emp in employees:
            SalarySlipFactory(employee=emp, salary_period="2026-05", status="pending_finance_review")

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.finance.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            result = payroll_bulk_approve(salary_period="2026-05", creator=user)
            assert len(result) == 3
