from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.finance.models import SalarySlip
from apps.hrm.models import EmploymentContract
from apps.hrm.services import employee_adjust_salary_apply
from apps.hrm.tests.factories import AttendanceFactory, EmployeeFactory, EmploymentContractFactory, SalarySlipFactory
from apps.inventory.tests.factories import RoleFactory, UserFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client):
    user = UserFactory(role=RoleFactory())
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
@patch("apps.common.xlib.permissions.PermissionChecker.check_permission", return_value=True)
class TestSalaryEndpoint:

    def test_adjust_salary_updates_active_contract_in_place(self, mock_check, auth_client):
        employee = EmployeeFactory(salary_base__create_contract=False)
        contract = EmploymentContractFactory.create(
            employee=employee,
            status="active",
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() + timedelta(days=20),
            salary_base=Decimal("10000000.00"),
        )

        url = f"/api/v1/hrm/employees/{employee.id}/adjust-salary/"
        data = {"new_salary_base": 15000000.00, "reason": "Tang luong truc tiep"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        assert contract.salary_base == Decimal("15000000.00")
        assert response.data["contract"]["salary_base"] == "15000000.00"

    def test_adjust_salary_creates_new_contract_when_active_expired(self, mock_check, auth_client):
        employee = EmployeeFactory(salary_base__create_contract=False)
        old_contract = EmploymentContractFactory.create(
            employee=employee,
            status="active",
            start_date=date.today() - timedelta(days=20),
            end_date=date.today() - timedelta(days=1),  # Expired yesterday
            salary_base=Decimal("10000000.00"),
        )

        url = f"/api/v1/hrm/employees/{employee.id}/adjust-salary/"
        data = {"new_salary_base": 15000000.00, "reason": "Tang luong voi HD moi"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Old contract should be expired (already expired naturally, but status is confirmed expired)
        old_contract.refresh_from_db()
        assert old_contract.status == "expired"

        # New contract should be created
        new_contracts = EmploymentContract.objects.filter(employee=employee, status="active")
        assert new_contracts.count() == 1
        new_c = new_contracts.first()
        assert new_c.salary_base == Decimal("15000000.00")
        assert new_c.start_date == date.today()

    def test_adjust_salary_recalculates_pending_payslip(self, mock_check, auth_client):
        employee = EmployeeFactory(salary_base__create_contract=False)
        today = date.today()
        # Create active contract
        EmploymentContractFactory.create(
            employee=employee,
            status="active",
            start_date=date(today.year, today.month, 1),
            salary_base=Decimal("10000000.00"),
        )

        # Create attendance for calculation
        for day in range(1, 21):
            AttendanceFactory.create(
                employee=employee, date=date(today.year, today.month, day), status="working", work_hours=Decimal("8.00")
            )

        # Create calculated slip (pending, status="calculated")
        slip = SalarySlipFactory.create(employee=employee, salary_period=today.strftime("%Y-%m"), status="calculated")

        url = f"/api/v1/hrm/employees/{employee.id}/adjust-salary/"
        data = {"new_salary_base": 15000000.00, "reason": "Adjust and recalculate"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Payslip should have been updated
        slip.refresh_from_db()
        assert len(response.data["affected_payslips"]) == 1
        assert response.data["affected_payslips"][0]["id"] == str(slip.id)

    def test_adjust_salary_skips_paid_payslip(self, mock_check, auth_client):
        employee = EmployeeFactory(salary_base__create_contract=False)
        today = date.today()
        EmploymentContractFactory.create(
            employee=employee,
            status="active",
            start_date=date(today.year, today.month, 1),
            salary_base=Decimal("10000000.00"),
        )

        slip = SalarySlipFactory.create(employee=employee, salary_period=today.strftime("%Y-%m"), status="paid")

        url = f"/api/v1/hrm/employees/{employee.id}/adjust-salary/"
        data = {"new_salary_base": 15000000.00, "reason": "Skip paid slip"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["affected_payslips"]) == 0

        slip.refresh_from_db()
        assert slip.status == "paid"  # Paid status not changed

    def test_old_url_update_salary_title_returns_404(self, mock_check, auth_client):
        employee = EmployeeFactory()
        url = f"/api/v1/hrm/employees/{employee.id}/update-salary-title/"
        data = {"new_salary_base": 15000000.00}
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND
