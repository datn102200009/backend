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

        assert response.status_code == status.HTTP_201_CREATED
        employee.refresh_from_db()
        assert employee.salary_base == 10000000.00

        history_id = response.data["id"]
        approve_url = f"/api/v1/hrm/employment-histories/{history_id}/approve/"
        approve_response = auth_client.post(approve_url)
        assert approve_response.status_code == status.HTTP_200_OK

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
        AttendanceFactory.create_batch(3)
        url = "/api/v1/hrm/attendances/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "results" in response.data
        assert response.data["count"] >= 3

        # Test limit and offset pagination
        response_paginated = auth_client.get(url, {"limit": 2, "offset": 1})
        assert response_paginated.status_code == status.HTTP_200_OK
        assert len(response_paginated.data["results"]) == 2

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
        LeaveRequestFactory.create_batch(3)
        url = "/api/v1/hrm/leave-requests/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "count" in response.data
        assert "results" in response.data
        assert response.data["count"] >= 3

        # Test limit and offset pagination
        response_paginated = auth_client.get(url, {"limit": 2, "offset": 1})
        assert response_paginated.status_code == status.HTTP_200_OK
        assert len(response_paginated.data["results"]) == 2

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
        employee = EmployeeFactory(salary_base=13000000.00)
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        # Add 10 working days
        for day in range(1, 11):
            AttendanceFactory(employee=employee, date=f"2026-05-{day:02d}", status="working", work_hours=8.00)

        url = f"/api/v1/hrm/salary-slips/{slip.id}/calculate/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert float(response.data["base_salary"]) > 0

    def test_approve_salary_slip_success(self, mock_check, auth_client):
        employee = EmployeeFactory()
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="calculated")

        url = f"/api/v1/hrm/salary-slips/{slip.id}/approve/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "approved"

        slip.refresh_from_db()
        assert slip.status == "approved"
        assert slip.approved_by is not None
        assert slip.approved_at is not None

    def test_approve_salary_slip_invalid_status(self, mock_check, auth_client):
        employee = EmployeeFactory()
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        url = f"/api/v1/hrm/salary-slips/{slip.id}/approve/"
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Chỉ có thể phê duyệt phiếu lương ở trạng thái 'Calculated'" in response.data["error"]

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
            status="approved",
        )
        SalarySlipFactory(
            employee=emp2,
            salary_period="2026-05",
            base_salary=6000000.00,
            net_pay=6000000.00,
            status="approved",
        )

        url = "/api/v1/hrm/salary-slips/bulk-confirm-pay/"
        data = {"salary_period": "2026-05", "payment_method": "bank_transfer"}

        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        assert response.data[0]["status"] == "paid"
        assert response.data[0]["payment_method"] == "bank_transfer"

        assert SalarySlip.objects.filter(salary_period="2026-05", status="paid").count() == 2

    def test_list_and_create_public_holiday(self, mock_check, auth_client):
        from datetime import timedelta

        from django.utils import timezone

        from apps.hrm.models import PublicHoliday

        PublicHoliday.objects.all().delete()

        # Test List empty
        url = "/api/v1/hrm/public-holidays/"
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 0

        # Test Create holiday (tương lai)
        tomorrow = (timezone.now() + timedelta(days=1)).date()
        data = {"name": "Giỗ tổ Hùng Vương", "start_date": str(tomorrow), "days": 1, "description": "Ngày Giỗ tổ"}
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Giỗ tổ Hùng Vương"
        assert PublicHoliday.objects.filter(start_date=tomorrow).exists()

        # Test List has 1
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_update_and_delete_public_holiday(self, mock_check, auth_client):
        from datetime import timedelta

        from django.utils import timezone

        from apps.hrm.models import PublicHoliday

        future_date = (timezone.now() + timedelta(days=2)).date()
        holiday = PublicHoliday.objects.create(name="Tết Dương Lịch", start_date=future_date, days=1)

        # Test update
        url = f"/api/v1/hrm/public-holidays/{holiday.id}/"
        data = {"name": "Tết Tây 2026", "start_date": str(future_date), "days": 3}
        response = auth_client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        holiday.refresh_from_db()
        assert holiday.name == "Tết Tây 2026"
        assert holiday.days == 3

        # Test delete
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not PublicHoliday.objects.filter(id=holiday.id).exists()

    def test_create_public_holiday_in_past_fails(self, mock_check, auth_client):
        from datetime import timedelta

        from django.utils import timezone

        url = "/api/v1/hrm/public-holidays/"
        yesterday = (timezone.now() - timedelta(days=1)).date()
        data = {"name": "Giỗ tổ Hùng Vương", "start_date": str(yesterday), "days": 1, "description": "Ngày Giỗ tổ"}
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Không được chọn ngày nghỉ lễ trong quá khứ." in response.data["error"]

    def test_update_public_holiday_to_past_fails(self, mock_check, auth_client):
        from datetime import timedelta

        from django.utils import timezone

        from apps.hrm.models import PublicHoliday

        future_date = (timezone.now() + timedelta(days=2)).date()
        holiday = PublicHoliday.objects.create(name="Tết Dương Lịch", start_date=future_date, days=1)

        url = f"/api/v1/hrm/public-holidays/{holiday.id}/"
        yesterday = (timezone.now() - timedelta(days=1)).date()
        data = {"start_date": str(yesterday)}
        response = auth_client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Không được chọn ngày nghỉ lễ trong quá khứ." in response.data["error"]

    def test_update_public_holiday_ongoing_or_past_fails(self, mock_check, auth_client):
        from django.utils import timezone

        from apps.hrm.models import PublicHoliday

        # Ngày nghỉ lễ đang diễn ra (bắt đầu hôm nay)
        today = timezone.now().date()
        holiday = PublicHoliday.objects.create(name="Tết Dương Lịch", start_date=today, days=1)

        url = f"/api/v1/hrm/public-holidays/{holiday.id}/"
        data = {"name": "Tết Dương Lịch Sửa Đổi"}
        response = auth_client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "Không được phép chỉnh sửa hoặc xóa ngày nghỉ lễ trong quá khứ hoặc đang diễn ra." in response.data["error"]
        )

    def test_delete_public_holiday_ongoing_or_past_fails(self, mock_check, auth_client):
        from django.utils import timezone

        from apps.hrm.models import PublicHoliday

        # Ngày nghỉ lễ đang diễn ra (bắt đầu hôm nay)
        today = timezone.now().date()
        holiday = PublicHoliday.objects.create(name="Tết Dương Lịch", start_date=today, days=1)

        url = f"/api/v1/hrm/public-holidays/{holiday.id}/"
        response = auth_client.delete(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "Không được phép chỉnh sửa hoặc xóa ngày nghỉ lễ trong quá khứ hoặc đang diễn ra." in response.data["error"]
        )

    def test_list_public_holidays_filter_by_year(self, mock_check, auth_client):
        from datetime import date, datetime, timedelta
        from unittest.mock import patch

        from django.utils import timezone

        this_year = timezone.now().year
        # Giả lập thời gian timezone.now() là ngày 15/06 của năm hiện tại để tránh flaky test cuối năm
        fixed_now = timezone.make_aware(datetime(this_year, 6, 15))

        with patch("django.utils.timezone.now", return_value=fixed_now):
            from apps.hrm.models import PublicHoliday

            PublicHoliday.objects.all().delete()

            # Tạo 2 ngày lễ ở các năm khác nhau (sử dụng ngày tương lai để pass validate)
            next_year = this_year + 1

            date1 = (timezone.now() + timedelta(days=5)).date()
            # Đảm bảo date2 ở năm sau
            date2 = date(next_year, 1, 1)

            PublicHoliday.objects.create(name="Lễ năm nay", start_date=date1, days=1)
            PublicHoliday.objects.create(name="Lễ năm sau", start_date=date2, days=1)

            url = "/api/v1/hrm/public-holidays/"

            # Test filter year hiện tại
            response = auth_client.get(url, {"year": this_year})
            assert response.status_code == 200
            assert len(response.data) == 1
            assert response.data[0]["name"] == "Lễ năm nay"

            # Test filter year sau
            response = auth_client.get(url, {"year": next_year})
            assert response.status_code == 200
            assert len(response.data) == 1
            assert response.data[0]["name"] == "Lễ năm sau"

    def test_list_public_holidays_filter_by_year_spanning(self, mock_check, auth_client):
        from datetime import date, datetime

        from django.utils import timezone

        from apps.hrm.models import PublicHoliday

        this_year = timezone.now().year
        fixed_now = timezone.make_aware(datetime(this_year, 6, 15))

        with patch("django.utils.timezone.now", return_value=fixed_now):
            PublicHoliday.objects.all().delete()

            # Create a holiday that starts Dec 30 of this year with 5 days
            # So it spans into next year (Dec 30, Dec 31, Jan 1, Jan 2, Jan 3)
            PublicHoliday.objects.create(name="Tết Tây Liên Năm", start_date=date(this_year, 12, 30), days=5)

            url = "/api/v1/hrm/public-holidays/"

            # Verify that filtering by this year includes the holiday
            response_this = auth_client.get(url, {"year": this_year})
            assert response_this.status_code == 200
            assert len(response_this.data) == 1
            assert response_this.data[0]["name"] == "Tết Tây Liên Năm"

            # Verify that filtering by next year also includes the holiday
            response_next = auth_client.get(url, {"year": this_year + 1})
            assert response_next.status_code == 200
            assert len(response_next.data) == 1
            assert response_next.data[0]["name"] == "Tết Tây Liên Năm"

    def test_salary_periods_list_view(self, mock_check, auth_client):
        from decimal import Decimal

        from apps.finance.models import SalarySlip
        from apps.hrm.tests.factories import EmployeeFactory

        emp1 = EmployeeFactory()
        emp2 = EmployeeFactory()
        # Clean up existing salary slips
        SalarySlip.objects.all().delete()

        SalarySlip.objects.create(
            name="SLIP-1",
            employee=emp1,
            salary_period="2026-05",
            base_salary=Decimal("5000.00"),
            gross_pay=Decimal("5000.00"),
            net_pay=Decimal("4500.00"),
            status="draft",
        )
        SalarySlip.objects.create(
            name="SLIP-2",
            employee=emp1,
            salary_period="2026-06",
            base_salary=Decimal("5000.00"),
            gross_pay=Decimal("5000.00"),
            net_pay=Decimal("4500.00"),
            status="draft",
        )
        SalarySlip.objects.create(
            name="SLIP-3",
            employee=emp2,
            salary_period="2026-05",
            base_salary=Decimal("5000.00"),
            gross_pay=Decimal("5000.00"),
            net_pay=Decimal("4500.00"),
            status="draft",
        )

        url = "/api/v1/hrm/salary-periods/"
        response = auth_client.get(url)
        assert response.status_code == 200
        assert response.data == ["2026-06", "2026-05"]
