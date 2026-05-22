from decimal import Decimal

import pytest
from django.contrib.auth.hashers import check_password

from apps.accounts.models import SystemLog, User
from apps.hrm.services import employee_create_with_user, employee_update
from apps.hrm.tests.factories import EmployeeFactory
from apps.inventory.tests.factories import RoleFactory, UserFactory
from apps.master_data.models import Employee


@pytest.mark.django_db
class TestEmployeeServices:

    def test_employee_create_without_user(self):
        # Arrange
        data = {
            "employee_id": "EMP9999",
            "full_name": "Nguyen Van A",
            "email": "vna@example.com",
            "phone": "0123456789",
            "gender": "male",
            "department": "IT",
            "position_title": "Developer",
            "salary_base": Decimal("15000000.00"),
            "is_union_member": True,
            "create_user": False,
        }

        # Act
        employee = employee_create_with_user(data=data, creator=None)

        # Assert
        assert employee is not None
        assert employee.employee_id == "EMP9999"
        assert employee.full_name == "Nguyen Van A"
        assert employee.employment_status == "active"
        assert not User.objects.filter(employee_id="EMP9999").exists()

        # Verify audit log
        log = SystemLog.objects.filter(table_name="employee", record_id=str(employee.id)).first()
        assert log is not None
        assert log.action == "create"
        assert log.new_value["employee_id"] == "EMP9999"
        assert log.new_value["full_name"] == "Nguyen Van A"

    def test_employee_create_with_user(self):
        # Arrange
        role = RoleFactory(name="Employee")
        data = {
            "employee_id": "EMP8888",
            "full_name": "Tran Thi B",
            "email": "ttb@example.com",
            "phone": "0987654321",
            "gender": "female",
            "department": "Sales",
            "position_title": "Sales Agent",
            "salary_base": Decimal("12000000.00"),
            "is_union_member": False,
            "create_user": True,
            "username": "tranthib",
            "password": "SecurePassword123",
            "role_id": str(role.id),
        }
        admin = UserFactory(username="admin_creator")

        # Act
        employee = employee_create_with_user(data=data, creator=admin)

        # Assert
        assert employee is not None
        assert employee.employee_id == "EMP8888"

        # Verify User was created and linked
        user = User.objects.filter(employee_id="EMP8888").first()
        assert user is not None
        assert user.username == "tranthib"
        assert user.email == "ttb@example.com"
        assert user.role == role
        assert check_password("SecurePassword123", user.password_hash)

        # Verify audit logs (should log both employee creation and user creation)
        emp_log = SystemLog.objects.filter(table_name="employee", record_id=str(employee.id), user=admin).first()
        assert emp_log is not None
        assert emp_log.action == "create"

        user_log = SystemLog.objects.filter(table_name="user", record_id=str(user.id), user=admin).first()
        assert user_log is not None
        assert user_log.action == "create"

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
