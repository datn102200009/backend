from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.common.xlib.exceptions import ValidationException
from apps.hrm.selectors import is_current_salary_period
from apps.hrm.services import payroll_bulk_submit_for_review, payroll_submit_for_review
from apps.hrm.tests.factories import EmployeeFactory, SalarySlipFactory


@pytest.fixture(autouse=True)
def mock_check_permission():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as m:
        m.return_value = True
        yield m


@pytest.mark.django_db
class TestCurrentPayrollPeriodBlock:

    def test_is_current_salary_period(self):
        """Kiểm tra helper is_current_salary_period hoạt động chính xác."""
        today = date(2026, 6, 19)
        assert is_current_salary_period("2026-06", today) is True
        assert is_current_salary_period("2026-05", today) is False
        assert is_current_salary_period("2026-07", today) is False

    def test_submit_blocked_for_current_period(self):
        """Kỳ hiện tại: submit bị chặn."""
        today = date(2026, 6, 19)
        current_period = "2026-06"
        employee = EmployeeFactory()
        slip = SalarySlipFactory(
            employee=employee,
            salary_period=current_period,
            status="calculated",
        )

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.hrm.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            with pytest.raises(ValidationException, match="tháng hiện tại"):
                payroll_submit_for_review(salary_slip_id=str(slip.id), user=None)

    def test_submit_allowed_for_previous_period(self):
        """Kỳ tháng trước: submit được phép."""
        previous_period = "2026-05"
        employee = EmployeeFactory()
        slip = SalarySlipFactory(
            employee=employee,
            salary_period=previous_period,
            status="calculated",
        )

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.hrm.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            result = payroll_submit_for_review(salary_slip_id=str(slip.id), user=None)
            assert result.status == "pending_finance_review"

    def test_submit_with_bypass_flag_works_for_current_period(self):
        """Bypass flag: cho phép submit FINAL slip kỳ hiện tại."""
        employee = EmployeeFactory()
        slip = SalarySlipFactory(
            employee=employee,
            salary_period="2026-06",
            status="calculated",
        )

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.hrm.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            result = payroll_submit_for_review(
                salary_slip_id=str(slip.id),
                user=None,
                bypass_current_period_check=True,
            )
            assert result.status == "pending_finance_review"

    def test_bulk_submit_blocked_for_current_period(self):
        """Bulk submit cũng bị chặn cho kỳ hiện tại."""
        employees = [EmployeeFactory() for _ in range(3)]
        for emp in employees:
            SalarySlipFactory(employee=emp, salary_period="2026-06", status="calculated")

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.hrm.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            with pytest.raises(ValidationException, match="tháng hiện tại"):
                payroll_bulk_submit_for_review(salary_period="2026-06", user=None)

    def test_bulk_submit_allowed_for_previous_period(self):
        """Bulk submit hoạt động bình thường với kỳ tháng trước."""
        employees = [EmployeeFactory() for _ in range(3)]
        for emp in employees:
            SalarySlipFactory(employee=emp, salary_period="2026-05", status="calculated")

        import datetime

        mock_now = datetime.datetime(2026, 6, 19, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch("apps.hrm.services.timezone.now") as mock_now_func:
            mock_now_func.return_value = mock_now
            result = payroll_bulk_submit_for_review(salary_period="2026-05", user=None)
            assert result["count"] == 3
