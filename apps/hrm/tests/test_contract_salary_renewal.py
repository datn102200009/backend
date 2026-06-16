from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.hrm.models import EmploymentContract
from apps.hrm.selectors import get_salary_at_date
from apps.hrm.services import contract_renew
from apps.hrm.tests.factories import EmployeeFactory, EmploymentContractFactory
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
@patch("apps.common.xlib.permissions.PermissionChecker.check_permission", return_value=True)
class TestContractSalaryRenewal:

    def test_renew_with_salary_increase_creates_history(self, mock_check):
        # Create employee and old contract
        employee = EmployeeFactory.create(salary_base__create_contract=False)
        admin = UserFactory.create(username="admin_renewer")
        old_contract = EmploymentContractFactory.create(
            employee=employee,
            contract_no="CON-OLD-1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 31),
            status="active",
            salary_base=Decimal("10000000.00"),
        )

        # Act
        result = contract_renew(
            contract_id=str(old_contract.id),
            new_contract_no="CON-NEW-1",
            new_contract_type="definite_term",
            start_date=date(2026, 6, 1),
            new_salary_base=Decimal("15000000.00"),
            renewer=admin,
        )

        new_contract = result["contract"]

        # Assert
        assert new_contract is not None
        assert new_contract.contract_no == "CON-NEW-1"
        assert new_contract.salary_base == Decimal("15000000.00")

    def test_renew_without_salary_keeps_old_salary(self, mock_check):
        # Create employee and old contract
        employee = EmployeeFactory.create(salary_base__create_contract=False)
        admin = UserFactory.create(username="admin_renewer_nosal")
        old_contract = EmploymentContractFactory.create(
            employee=employee,
            contract_no="CON-OLD-2",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 31),
            status="active",
            salary_base=Decimal("10000000.00"),
        )

        # Act
        result = contract_renew(
            contract_id=str(old_contract.id),
            new_contract_no="CON-NEW-2",
            new_contract_type="definite_term",
            start_date=date(2026, 6, 1),
            renewer=admin,
        )

        new_contract = result["contract"]

        # Assert
        assert new_contract is not None
        assert new_contract.contract_no == "CON-NEW-2"
        # Keeps old salary_base since no new_salary_base was provided
        assert new_contract.salary_base == Decimal("10000000.00")

    def test_salary_at_date_uses_latest_history(self, mock_check):
        # Create employee and old contract
        employee = EmployeeFactory.create(salary_base__create_contract=False)
        admin = UserFactory.create(username="admin_renewer_latest")
        old_contract = EmploymentContractFactory.create(
            employee=employee,
            contract_no="CON-OLD-3",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 31),
            status="active",
            salary_base=Decimal("10000000.00"),
        )

        # Renew with salary increase
        contract_renew(
            contract_id=str(old_contract.id),
            new_contract_no="CON-NEW-3",
            new_contract_type="definite_term",
            start_date=date(2026, 6, 1),
            new_salary_base=Decimal("15000000.00"),
            renewer=admin,
        )

        # Verify salary at date after change
        assert get_salary_at_date(employee, date(2026, 5, 15)) == Decimal("10000000.00")
        assert get_salary_at_date(employee, date(2026, 6, 15)) == Decimal("15000000.00")
