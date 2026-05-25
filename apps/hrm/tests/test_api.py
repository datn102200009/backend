from datetime import date
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.finance.models import SalarySlip
from apps.hrm.models import Attendance, DisciplineRecord, EmploymentContract, LeaveRequest, RewardRecord
from apps.hrm.tests.factories import (
    AttendanceFactory,
    DisciplineRecordFactory,
    EmployeeFactory,
    EmploymentContractFactory,
    LeaveRequestFactory,
    RewardRecordFactory,
    SalarySlipFactory,
)
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
class TestHrmAPI:

    # =========================================================================
    # EMPLOYEE API TESTS
    # =========================================================================

    def test_list_employees(self, mock_check, auth_client):
        EmployeeFactory.create_batch(3)
        url = "/api/v1/hrm/employees/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 3

    def test_create_employee(self, mock_check, auth_client):
        url = "/api/v1/hrm/employees/create/"
        data = {
            "employee_id": "EMP8888",
            "full_name": "Nguyen Van Test",
            "department": "IT",
            "position_title": "Developer",
            "salary_base": 15000000.00,
            "is_union_member": True,
            "email": "testemail8888@example.com",
            "phone": "0123456789",
            "gender": "male",
            "date_of_birth": "1995-10-10",
            "join_date": "2026-01-01",
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["employee_id"] == "EMP8888"
        assert Employee.objects.filter(employee_id="EMP8888").exists()

    def test_create_employee_with_user(self, mock_check, auth_client):
        url = "/api/v1/hrm/employees/create/"
        role = RoleFactory()
        data = {
            "employee_id": "EMP9999",
            "full_name": "Tran Thi User",
            "salary_base": 12000000.00,
            "create_user": True,
            "username": "tranthiuser",
            "password": "secretpassword123",
            "role_id": str(role.id),
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["employee_id"] == "EMP9999"

        # Verify user account creation
        from apps.accounts.models import User

        assert User.objects.filter(username="tranthiuser", employee_id="EMP9999").exists()

    def test_detail_employee(self, mock_check, auth_client):
        employee = EmployeeFactory()
        url = f"/api/v1/hrm/employees/{employee.id}/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["employee_id"] == employee.employee_id
        # detail output should have relations
        assert "contracts" in response.data
        assert "employment_histories" in response.data

    def test_update_employee(self, mock_check, auth_client):
        employee = EmployeeFactory(full_name="Old Name", department="Sales")
        url = f"/api/v1/hrm/employees/{employee.id}/update/"
        data = {"full_name": "New Name", "department": "Marketing"}

        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["full_name"] == "New Name"

        employee.refresh_from_db()
        assert employee.full_name == "New Name"
        assert employee.department == "Marketing"

    def test_update_salary_title(self, mock_check, auth_client):
        employee = EmployeeFactory(salary_base=10000000.00, position_title="Staff")
        url = f"/api/v1/hrm/employees/{employee.id}/update-salary-title/"
        data = {
            "change_type": "salary_change",
            "new_salary_base": 12500000.00,
            "effective_date": "2026-06-01",
            "reason": "Tang luong theo nang luc",
        }

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        employee.refresh_from_db()
        assert employee.salary_base == 12500000.00

        # Verify employment history was written
        assert employee.employment_histories.filter(change_type="salary_change").exists()

    # =========================================================================
    # CONTRACT API TESTS
    # =========================================================================

    def test_create_or_renew_contract(self, mock_check, auth_client):
        employee = EmployeeFactory()
        url = "/api/v1/hrm/contracts/"
        data = {
            "employee_id": str(employee.id),
            "contract_no": "CONTRACT-NEW-99",
            "contract_type": "definite_term",
            "start_date": "2026-06-01",
            "end_date": "2027-05-31",
            "note": "Hop dong lao dong moi",
        }

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["contract_no"] == "CONTRACT-NEW-99"
        assert EmploymentContract.objects.filter(contract_no="CONTRACT-NEW-99").exists()

    def test_terminate_contract(self, mock_check, auth_client):
        employee = EmployeeFactory(employment_status="active")
        contract = EmploymentContractFactory(employee=employee, status="active")
        url = f"/api/v1/hrm/contracts/{contract.id}/terminate/"
        data = {
            "termination_date": "2026-06-15",
            "reason": "Nghi viec theo nguyen vong",
        }

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        assert contract.status == "terminated"
        assert contract.end_date == date(2026, 6, 15)

        employee.refresh_from_db()
        assert employee.employment_status == "inactive"
        assert employee.leave_date == date(2026, 6, 15)

    # =========================================================================
    # ATTENDANCE API TESTS
    # =========================================================================

    def test_list_attendances(self, mock_check, auth_client):
        AttendanceFactory.create_batch(2)
        url = "/api/v1/hrm/attendances/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_batch_attendance(self, mock_check, auth_client):
        employee1 = EmployeeFactory()
        employee2 = EmployeeFactory()
        url = "/api/v1/hrm/attendances/batch/"
        data = {
            "date": "2026-05-20",
            "records": [
                {
                    "employee_id": str(employee1.id),
                    "status": "working",
                    "work_hours": 8.00,
                    "overtime_hours": 2.00,
                    "remarks": "OT 2 tieng",
                },
                {
                    "employee_id": str(employee2.id),
                    "status": "paid_leave",
                    "work_hours": 0.00,
                    "overtime_hours": 0.00,
                },
            ],
        }

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 2
        assert Attendance.objects.filter(employee=employee1, date="2026-05-20", status="working").exists()
        assert Attendance.objects.filter(employee=employee2, date="2026-05-20", status="paid_leave").exists()

    # =========================================================================
    # LEAVE REQUEST API TESTS
    # =========================================================================

    def test_list_leave_requests(self, mock_check, auth_client):
        LeaveRequestFactory.create_batch(2)
        url = "/api/v1/hrm/leave-requests/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_create_leave_request(self, mock_check, auth_client):
        employee = EmployeeFactory()
        url = "/api/v1/hrm/leave-requests/create/"
        data = {
            "employee_id": str(employee.id),
            "leave_type": "paid",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "days": 2.0,
            "reason": "Nghi nghi mat gia dinh",
        }

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "pending"
        assert LeaveRequest.objects.filter(employee=employee, start_date="2026-06-01").exists()

    def test_approve_leave_request(self, mock_check, auth_client):
        leave_request = LeaveRequestFactory(
            status="pending", leave_type="paid", start_date="2026-05-01", end_date="2026-05-01", days=1.0
        )
        url = f"/api/v1/hrm/leave-requests/{leave_request.id}/approve/"
        data = {"action": "approve"}

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        leave_request.refresh_from_db()
        assert leave_request.status == "approved"

        # Verify sync to Attendance
        assert Attendance.objects.filter(
            employee=leave_request.employee, date="2026-05-01", status="paid_leave"
        ).exists()

    def test_reject_leave_request(self, mock_check, auth_client):
        leave_request = LeaveRequestFactory(status="pending")
        url = f"/api/v1/hrm/leave-requests/{leave_request.id}/approve/"
        data = {"action": "reject"}

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        leave_request.refresh_from_db()
        assert leave_request.status == "rejected"

    # =========================================================================
    # SALARY SLIP API TESTS
    # =========================================================================

    def test_list_salary_slips(self, mock_check, auth_client):
        SalarySlipFactory.create_batch(2)
        url = "/api/v1/hrm/salary-slips/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2

    def test_initialize_salary_slips(self, mock_check, auth_client):
        # Clear slips first
        SalarySlip.objects.all().delete()

        # Ensure active employee exists
        EmployeeFactory(employment_status="active")

        url = "/api/v1/hrm/salary-slips/initialize/"
        data = {"salary_period": "2026-06"}

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) >= 1
        assert SalarySlip.objects.filter(salary_period="2026-06").exists()

    def test_calculate_salary_slip(self, mock_check, auth_client):
        employee = EmployeeFactory(salary_base=13000000.00, is_union_member=True)
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        # Add 10 working days
        for day in range(1, 11):
            AttendanceFactory(employee=employee, date=f"2026-05-{day:02d}", status="working", work_hours=8.00)

        url = f"/api/v1/hrm/salary-slips/{slip.id}/calculate/"
        data = {"standard_days": 26}

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert float(response.data["base_salary"]) > 0
        assert float(response.data["union_fee_2pct"]) == 260000.00  # 2% of 13m

    def test_confirm_salary_slip(self, mock_check, auth_client):
        employee = EmployeeFactory(salary_base=5000000.00)
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", net_pay=5000000.00, status="draft")
        url = f"/api/v1/hrm/salary-slips/{slip.id}/confirm/"
        data = {"payment_method": "bank_transfer"}

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        slip.refresh_from_db()
        assert slip.status == "paid"
        assert slip.payment_method == "bank_transfer"

        # Verify CashFlowTransaction integration
        from apps.finance.models import CashFlowTransaction

        assert CashFlowTransaction.objects.filter(name=f"PAY-SALARY-{employee.employee_id}-2026-05").exists()

    # =========================================================================
    # REWARDS & DISCIPLINES API TESTS
    # =========================================================================

    def test_create_reward(self, mock_check, auth_client):
        employee = EmployeeFactory()
        url = "/api/v1/hrm/rewards/"
        data = {
            "employee_id": str(employee.id),
            "reward_date": "2026-05-15",
            "reward_type": "performance_bonus",
            "amount": 2000000.00,
            "description": "Sáng kiến cải tiến sản xuất",
        }

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["reward_type"] == "performance_bonus"
        assert RewardRecord.objects.filter(employee=employee, amount=2000000.00).exists()

    def test_create_discipline(self, mock_check, auth_client):
        employee = EmployeeFactory()
        url = "/api/v1/hrm/disciplines/"
        data = {
            "employee_id": str(employee.id),
            "incident_date": "2026-05-12",
            "discipline_date": "2026-05-14",
            "discipline_type": "warning",
            "penalty_amount": 300000.00,
            "description": "Không mang thẻ nhân viên",
        }

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["discipline_type"] == "warning"
        assert DisciplineRecord.objects.filter(employee=employee, penalty_amount=300000.00).exists()

    def test_list_rewards(self, mock_check, auth_client):
        employee = EmployeeFactory()
        RewardRecordFactory.create_batch(2, employee=employee)
        url = "/api/v1/hrm/rewards/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2
        assert "employee_code" in response.data[0]
        assert "employee_name" in response.data[0]

    def test_list_disciplines(self, mock_check, auth_client):
        employee = EmployeeFactory()
        DisciplineRecordFactory.create_batch(2, employee=employee)
        url = "/api/v1/hrm/disciplines/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2
        assert "employee_code" in response.data[0]
        assert "employee_name" in response.data[0]

    def test_bulk_confirm_salary_slips(self, mock_check, auth_client):
        # Clear slips first
        SalarySlip.objects.all().delete()

        emp1 = EmployeeFactory(employee_id="EMP9501", full_name="Emp 1")
        emp2 = EmployeeFactory(employee_id="EMP9502", full_name="Emp 2")

        SalarySlipFactory(
            employee=emp1,
            salary_period="2026-05",
            base_salary=5000000.00,
            net_pay=5000000.00,
            status="draft",
        )
        SalarySlipFactory(
            employee=emp2,
            salary_period="2026-05",
            base_salary=6000000.00,
            net_pay=6000000.00,
            status="draft",
        )

        url = "/api/v1/hrm/salary-slips/bulk-confirm-pay/"
        data = {"salary_period": "2026-05", "payment_method": "bank_transfer"}

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        assert response.data[0]["status"] == "paid"
        assert response.data[0]["payment_method"] == "bank_transfer"

        assert SalarySlip.objects.filter(salary_period="2026-05", status="paid").count() == 2
