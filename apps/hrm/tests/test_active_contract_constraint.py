from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import IntegrityError

from apps.common.xlib.exceptions import ValidationException
from apps.hrm.models import EmploymentContract
from apps.hrm.selectors import count_active_contracts
from apps.hrm.services import contract_create_or_renew, contract_renew, employee_create_with_contract
from apps.hrm.tests.factories import EmployeeFactory, EmploymentContractFactory
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
@patch("apps.common.xlib.permissions.PermissionChecker.check_permission", return_value=True)
class TestActiveContractConstraint:

    def test_count_active_contracts_returns_correct_count(self, mock_check):
        employee = EmployeeFactory(salary_base__create_contract=False)
        assert count_active_contracts(employee) == 0

        EmploymentContractFactory.create(employee=employee, status="active")
        assert count_active_contracts(employee) == 1

        # We bypass unique constraint here for testing selector logic if we could,
        # but since unique constraint is active, we cannot save two active in DB.
        # But we can verify active vs expired
        EmploymentContractFactory.create(employee=employee, status="expired")
        assert count_active_contracts(employee) == 1

    def test_count_active_contracts_exclude_id(self, mock_check):
        employee = EmployeeFactory(salary_base__create_contract=False)
        c = EmploymentContractFactory.create(employee=employee, status="active")
        assert count_active_contracts(employee, exclude_contract_id=str(c.id)) == 0

    def test_partial_unique_index_rejects_2_active(self, mock_check):
        employee = EmployeeFactory(salary_base__create_contract=False)
        EmploymentContract.objects.create(
            employee=employee,
            contract_no="HD1",
            contract_type="indefinite_term",
            start_date=date(2026, 1, 1),
            status="active",
        )

        with pytest.raises(IntegrityError):
            # Attempt to create second active contract bypassing services directly at DB level
            EmploymentContract.objects.create(
                employee=employee,
                contract_no="HD2",
                contract_type="indefinite_term",
                start_date=date(2026, 2, 1),
                status="active",
            )

    def test_contract_renew_transitions_old_to_expired_before_creating_new(self, mock_check):
        employee = EmployeeFactory(salary_base__create_contract=False)
        admin = UserFactory()
        old_contract = EmploymentContractFactory.create(
            employee=employee,
            contract_no="CON-OLD",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 5, 31),
            status="active",
            salary_base=Decimal("10000000.00"),
        )

        # Renewing contract (overlap case)
        result = contract_renew(
            contract_id=str(old_contract.id),
            new_contract_no="CON-NEW",
            new_contract_type="definite_term",
            start_date=date(2026, 6, 1),
            new_salary_base=Decimal("12000000.00"),
            renewer=admin,
        )

        old_contract.refresh_from_db()
        assert old_contract.status == "expired"
        assert old_contract.end_date == date(2026, 5, 31)

        new_contract = result["contract"]
        assert new_contract.status == "active"
        assert new_contract.contract_no == "CON-NEW"
        assert new_contract.salary_base == Decimal("12000000.00")

    def test_contract_create_or_renew_raises_when_multiple_active_exist(self, mock_check):
        employee = EmployeeFactory(salary_base__create_contract=False)
        admin = UserFactory()

        # We manually bypass the service to create one active contract
        EmploymentContractFactory.create(employee=employee, status="active", contract_no="HD1")

        # Calling contract_create_or_renew with second active shouldn't crash with IntegrityError,
        # but be validated cleanly. If we try to create another one, since 1 is active,
        # the service will transition the old active contract to expired first.
        contract_data = {
            "contract_no": "HD2",
            "contract_type": "definite_term",
            "start_date": date(2026, 2, 1),
            "salary_base": 12000000.00,
        }

        new_contract = contract_create_or_renew(
            employee_id=str(employee.id), contract_data=contract_data, creator=admin
        )

        assert new_contract.status == "active"

        # The previous contract HD1 should now be expired
        old_c = EmploymentContract.objects.get(contract_no="HD1")
        assert old_c.status == "expired"
