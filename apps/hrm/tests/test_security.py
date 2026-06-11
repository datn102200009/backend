from datetime import date
from decimal import Decimal

import pytest

from apps.accounts.models import Permission, RolePermission
from apps.common.xlib.exceptions import PermissionException
from apps.hrm.services import (
    attendance_batch_record,
    contract_create_or_renew,
    contract_terminate,
    discipline_record_create,
    employee_create_with_user,
    employee_update,
    employee_update_salary_or_title,
    leave_request_approve,
    leave_request_create,
    payroll_calculate_salary,
    payroll_initialize_period,
    reward_record_create,
)
from apps.hrm.tests.factories import EmployeeFactory, EmploymentContractFactory, LeaveRequestFactory, SalarySlipFactory
from apps.inventory.tests.factories import RoleFactory, UserFactory


def create_user_with_permission(permission_code: str):
    role = RoleFactory()
    permission, _ = Permission.objects.get_or_create(code=permission_code, defaults={"name": f"Test {permission_code}"})
    RolePermission.objects.create(role=role, permission=permission)
    return UserFactory(role=role)


@pytest.mark.django_db
class TestHRMSecurity:

    def test_leave_request_create_permission(self):
        # User without permission should raise PermissionException
        unauthorized_user = UserFactory()
        employee = EmployeeFactory()
        data = {
            "leave_type": "sick",
            "start_date": date(2026, 5, 10),
            "end_date": date(2026, 5, 12),
            "days": Decimal("3.0"),
            "reason": "Sick leave",
        }
        with pytest.raises(PermissionException) as exc_info:
            leave_request_create(employee_id=employee.id, data=data, creator=unauthorized_user)
        assert "hrm.add_leaverequest" in str(exc_info.value)

        # User with permission should pass permission check
        authorized_user = create_user_with_permission("hrm.add_leaverequest")
        req = leave_request_create(employee_id=employee.id, data=data, creator=authorized_user)
        assert req is not None

    def test_leave_request_approve_permission(self):
        unauthorized_user = UserFactory()
        request = LeaveRequestFactory(status="pending")

        with pytest.raises(PermissionException) as exc_info:
            leave_request_approve(
                leave_request_id=request.id,
                approved_by_user_id=str(unauthorized_user.id),
                approved_by=unauthorized_user,
            )
        assert "hrm.change_leaverequest" in str(exc_info.value)

        authorized_user = create_user_with_permission("hrm.change_leaverequest")
        approved_req = leave_request_approve(
            leave_request_id=request.id,
            approved_by_user_id=str(authorized_user.id),
            approved_by=authorized_user,
        )
        assert approved_req.status == "approved"

    def test_employee_update_salary_or_title_permission(self):
        unauthorized_user = UserFactory()
        employee = EmployeeFactory(salary_base=Decimal("10000000.00"))
        change_data = {
            "change_type": "salary_change",
            "new_salary_base": Decimal("13000000.00"),
            "effective_date": date(2026, 6, 1),
            "reason": "Performance bonus",
        }

        with pytest.raises(PermissionException) as exc_info:
            employee_update_salary_or_title(
                employee_id=employee.id,
                change_data=change_data,
                approved_by_user_id=str(unauthorized_user.id),
                approved_by=unauthorized_user,
            )
        assert "hrm.change_employee" in str(exc_info.value)

        authorized_user = create_user_with_permission("hrm.change_employee")
        history = employee_update_salary_or_title(
            employee_id=employee.id,
            change_data=change_data,
            approved_by_user_id=str(authorized_user.id),
            approved_by=authorized_user,
        )
        assert history.new_salary_base == Decimal("13000000.00")
        assert history.status == "pending_approval"

        # Approve proposal
        from apps.hrm.services import employment_history_approve

        employment_history_approve(user=authorized_user, history_id=str(history.id))

        employee.refresh_from_db()
        assert employee.salary_base == Decimal("13000000.00")

    def test_reward_record_create_permission(self):
        unauthorized_user = UserFactory()
        employee = EmployeeFactory()
        data = {
            "reward_date": date(2026, 5, 23),
            "reward_type": "performance_bonus",
            "amount": 500000.00,  # float input to test casting
            "description": "Exemplary performance",
        }

        with pytest.raises(PermissionException) as exc_info:
            reward_record_create(employee_id=employee.id, data=data, creator=unauthorized_user)
        assert "hrm.add_rewardrecord" in str(exc_info.value)

        authorized_user = create_user_with_permission("hrm.add_rewardrecord")
        reward = reward_record_create(employee_id=employee.id, data=data, creator=authorized_user)
        assert reward.amount == Decimal("500000.00")

    def test_discipline_record_create_permission(self):
        unauthorized_user = UserFactory()
        employee = EmployeeFactory()
        data = {
            "incident_date": date(2026, 5, 22),
            "discipline_date": date(2026, 5, 23),
            "discipline_type": "warning",
            "description": "Lateness",
            "penalty_amount": 100000.00,  # float input to test casting
        }

        with pytest.raises(PermissionException) as exc_info:
            discipline_record_create(employee_id=employee.id, data=data, creator=unauthorized_user)
        assert "hrm.add_disciplinerecord" in str(exc_info.value)

        authorized_user = create_user_with_permission("hrm.add_disciplinerecord")
        discipline = discipline_record_create(employee_id=employee.id, data=data, creator=authorized_user)
        assert discipline.penalty_amount == Decimal("100000.00")
