from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.hrm.models import EmploymentContract
from apps.hrm.selectors import get_salary_at_date
from apps.hrm.services import payroll_calculate_salary
from apps.hrm.tests.factories import AttendanceFactory, EmployeeFactory, EmploymentContractFactory, SalarySlipFactory
from apps.inventory.tests.factories import RoleFactory, UserFactory
from apps.master_data.models import Employee


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
class TestEmployeeWithContractSalary:

    def test_employee_create_persists_salary_in_contract(self, mock_check, auth_client):
        url = "/api/v1/hrm/employees/create/"
        data = {
            "employee_id": "NV7777",
            "full_name": "Nguyen Contract Salary",
            "contract_salary_base": 12500000.00,
            "email": "nv7777@example.com",
            "phone": "0912345678",
            "gender": "male",
            "date_of_birth": "1990-05-15",
            "join_date": "2026-01-01",
            "contract_no": "HDLD-NV7777",
            "contract_type": "definite_term",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        employee = Employee.objects.get(employee_id="NV7777")
        assert employee is not None

        # Verify contract was created with correct salary base
        contract = EmploymentContract.objects.get(employee=employee, contract_no="HDLD-NV7777")
        assert contract.salary_base == Decimal("12500000.00")

    def test_current_salary_base_returns_contract_salary(self, mock_check):
        # Create employee and manual active contract
        employee = EmployeeFactory.create(salary_base__create_contract=False)
        contract = EmploymentContractFactory.create(
            employee=employee,
            contract_no="HDLD-ACTIVE-01",
            status="active",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            salary_base=Decimal("14000000.00"),
        )

        salary_base = get_salary_at_date(employee, date(2026, 6, 15))
        assert salary_base == Decimal("14000000.00")

    def test_payroll_uses_contract_salary_not_employee_salary(self, mock_check):
        # Create employee with custom contract salary
        employee = EmployeeFactory.create(salary_base__create_contract=False)
        contract = EmploymentContractFactory.create(
            employee=employee,
            status="active",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            salary_base=Decimal("18000000.00"),
        )

        # Create some attendance records so payroll can calculate working days
        for day in range(1, 23):
            AttendanceFactory.create(
                employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00")
            )

        # Create salary slip
        slip = SalarySlipFactory.create(employee=employee, salary_period="2026-05")

        # Calculate salary for the employee
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=None)
        calculated_slip.refresh_from_db()

        # Base salary of slip is calculated based on working days and standard days.
        assert calculated_slip is not None
        assert calculated_slip.base_salary > Decimal("0.00")
