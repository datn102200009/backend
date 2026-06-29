from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import SystemLog, User
from apps.hrm.services import employee_create_with_contract, employee_update
from apps.hrm.tests.factories import EmployeeFactory
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestEmployeeServices:

    def test_employee_create_without_user(self):
        # Arrange
        data = {
            "employee_id": "NV9999",
            "full_name": "Nguyen Van A",
            "email": "vna@example.com",
            "phone": "0123456789",
            "gender": "male",
        }
        contract_data = {
            "contract_no": "HDLD-NV9999",
            "contract_type": "definite_term",
            "start_date": date(2026, 1, 1),
            "end_date": date(2027, 1, 1),
            "salary_base": Decimal("15000000.00"),
        }

        # Act
        employee, contract = employee_create_with_contract(data=data, contract_data=contract_data, creator=None)

        # Assert
        assert employee is not None
        assert employee.employee_id == "NV9999"
        assert employee.full_name == "Nguyen Van A"
        assert employee.employment_status == "active"
        assert contract is not None
        assert contract.contract_no == "HDLD-NV9999"
        assert not User.objects.filter(employee_id="NV9999").exists()

        # Verify audit log
        log = SystemLog.objects.filter(table_name="employee", record_id=str(employee.id)).first()
        assert log is not None
        assert log.action == "create"
        assert log.new_value["employee_id"] == "NV9999"
        assert log.new_value["full_name"] == "Nguyen Van A"

    def test_employee_create_with_contract(self):
        # Arrange
        data = {
            "employee_id": "NV7777",
            "full_name": "Le Van C",
            "email": "lvc@example.com",
            "phone": "0912345678",
            "gender": "male",
        }
        contract_data = {
            "contract_no": "HDLD-2026-NV7",
            "contract_type": "definite_term",
            "start_date": date(2026, 6, 16),
            "end_date": date(2027, 6, 16),
            "note": "Hợp đồng lao động mẫu",
            "file_url": "http://example.com/lvc.pdf",
            "salary_base": Decimal("10000000.00"),
        }
        admin = UserFactory(username="admin_contract_creator")

        # Act
        employee, contract = employee_create_with_contract(data=data, contract_data=contract_data, creator=admin)

        # Assert
        assert employee is not None
        assert employee.employee_id == "NV7777"
        assert contract is not None
        assert contract.contract_no == "HDLD-2026-NV7"
        assert contract.employee == employee
        assert contract.contract_type == "definite_term"
        assert contract.status == "active"

        # Verify audit logs
        emp_log = SystemLog.objects.filter(table_name="employee", record_id=str(employee.id), user=admin).first()
        assert emp_log is not None
        contract_log = SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(contract.id), user=admin
        ).first()
        assert contract_log is not None

    def test_employee_update_basic_info(self):
        # Arrange
        employee = EmployeeFactory(full_name="Old Name", email="old@example.com", phone="111111", address="Old Address")
        admin = UserFactory(username="admin_updater")
        update_data = {"full_name": "New Name", "email": "new@example.com", "address": "New Address"}

        # Act
        updated_emp = employee_update(employee=employee, data=update_data, updater=admin)

        # Assert
        assert updated_emp.full_name == "New Name"
        assert updated_emp.email == "new@example.com"
        assert updated_emp.address == "New Address"
        assert updated_emp.phone == "111111"  # Should remain unchanged

        # Verify audit log with old and new values
        log = SystemLog.objects.filter(table_name="employee", record_id=str(employee.id), user=admin).first()
        assert log is not None
        assert log.action == "update"
        assert log.old_value["full_name"] == "Old Name"
        assert log.old_value["email"] == "old@example.com"
        assert log.old_value["address"] == "Old Address"
        assert log.new_value["full_name"] == "New Name"
        assert log.new_value["email"] == "new@example.com"
        assert log.new_value["address"] == "New Address"
