from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.finance.models import CashFlowTransaction, SalarySlip
from apps.hrm.tests.factories import EmployeeFactory, SalarySlipFactory
from apps.inventory.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestFinancePayrollAPIViews:

    @pytest.fixture
    def authenticated_client(self):
        user = UserFactory()
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_approve_salary_slip_api(self, mock_permission_checker, authenticated_client):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_API_1")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")
        url = reverse("salary-slip-approve", kwargs={"id": slip.id})

        # Act
        response = authenticated_client.post(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "approved"
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.payroll_approve")

    def test_reject_salary_slip_api(self, mock_permission_checker, authenticated_client):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_API_2")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")
        url = reverse("salary-slip-reject", kwargs={"id": slip.id})
        data = {"reason": "Lý do từ chối quá dài để hợp lệ"}

        # Act
        response = authenticated_client.post(url, data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "calculated"
        assert response.data["remarks"] == "Lý do từ chối quá dài để hợp lệ"
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.payroll_approve")

    def test_reject_salary_slip_short_reason_api(self, mock_permission_checker, authenticated_client):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_API_3")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")
        url = reverse("salary-slip-reject", kwargs={"id": slip.id})
        data = {"reason": "Ngắn"}

        # Act
        response = authenticated_client.post(url, data)

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_pay_salary_slip_api(self, mock_permission_checker, authenticated_client):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP_API_4")
        slip = SalarySlipFactory(
            employee=employee,
            salary_period="2026-05",
            status="approved",
            net_pay=Decimal("5000000.00"),
        )
        url = reverse("salary-slip-pay", kwargs={"id": slip.id})
        data = {"payment_method": "bank_transfer"}

        # Act
        response = authenticated_client.post(url, data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "paid"
        assert response.data["payment_method"] == "bank_transfer"
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.change_salaryslip")

    def test_bulk_approve_pay_salary_slip_api(self, mock_permission_checker, authenticated_client):
        # Arrange
        emp1 = EmployeeFactory(employee_id="EMP_API_5")
        emp2 = EmployeeFactory(employee_id="EMP_API_6")
        emp3 = EmployeeFactory(employee_id="EMP_API_7")
        SalarySlipFactory(
            employee=emp1,
            salary_period="2026-06",
            status="pending_finance_review",
            net_pay=Decimal("3000000.00"),
        )
        SalarySlipFactory(
            employee=emp2,
            salary_period="2026-06",
            status="calculated",
            net_pay=Decimal("4000000.00"),
        )
        SalarySlipFactory(
            employee=emp3,
            salary_period="2026-06",
            status="approved",
            net_pay=Decimal("2000000.00"),
        )
        url = reverse("salary-slip-bulk-approve-pay")
        data = {"salary_period": "2026-06", "payment_method": "cash"}

        # Act
        response = authenticated_client.post(url, data)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        mock_permission_checker.assert_any_call(authenticated_client.handler._force_user, "finance.change_salaryslip")
