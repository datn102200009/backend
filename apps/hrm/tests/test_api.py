from datetime import date
from decimal import Decimal
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
            "employee_id": "NV8888",
            "full_name": "Nguyen Van Test",
            "contract_salary_base": 15000000.00,
            "email": "testemail8888@example.com",
            "phone": "0123456789",
            "gender": "male",
            "date_of_birth": "1995-10-10",
            "join_date": "2026-01-01",
            "contract_no": "HDLD-2026-NV8",
            "contract_type": "definite_term",
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2027-01-01",
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["employee"]["employee_id"] == "NV8888"
        assert response.data["contract"] is not None
        assert response.data["contract"]["contract_no"] == "HDLD-2026-NV8"
        assert Employee.objects.filter(employee_id="NV8888").exists()

    def test_create_employee_with_contract(self, mock_check, auth_client):
        from apps.hrm.models import EmploymentContract

        url = "/api/v1/hrm/employees/create/"
        data = {
            "employee_id": "NV7777",
            "full_name": "Nguyen Van Contract",
            "contract_salary_base": 15000000.00,
            "email": "testcontract7777@example.com",
            "phone": "0123456789",
            "gender": "male",
            "date_of_birth": "1995-10-10",
            "join_date": "2026-06-16",
            "create_contract": True,
            "contract_no": "HDLD-2026-NV7",
            "contract_type": "definite_term",
            "contract_start_date": "2026-06-16",
            "contract_end_date": "2027-06-16",
            "contract_note": "Gia hạn hợp đồng mẫu",
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["employee"]["employee_id"] == "NV7777"
        assert response.data["contract"] is not None
        assert response.data["contract"]["contract_no"] == "HDLD-2026-NV7"
        assert Employee.objects.filter(employee_id="NV7777").exists()
        assert EmploymentContract.objects.filter(contract_no="HDLD-2026-NV7").exists()

    def test_detail_employee(self, mock_check, auth_client):
        employee = EmployeeFactory()
        url = f"/api/v1/hrm/employees/{employee.id}/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["employee_id"] == employee.employee_id
        # detail output should have relations
        assert "contracts" in response.data

    def test_update_employee(self, mock_check, auth_client):
        employee = EmployeeFactory(full_name="Old Name")
        url = f"/api/v1/hrm/employees/{employee.id}/update/"
        data = {"full_name": "New Name"}

        response = auth_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["full_name"] == "New Name"

        employee.refresh_from_db()
        assert employee.full_name == "New Name"

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

        # Check slip status
        from apps.finance.models import SalarySlip

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-06")
        assert slip.status == "pending_finance_review"

    def test_contract_terminate_api_returns_pending_finance_review_status(self, mock_check, auth_client):
        employee = EmployeeFactory(employment_status="active")
        contract = EmploymentContractFactory(employee=employee, status="active")
        url = f"/api/v1/hrm/contracts/{contract.id}/terminate/"
        data = {
            "termination_date": "2026-06-15",
            "reason": "Nghi viec theo nguyen vong",
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK

        from apps.finance.models import SalarySlip

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-06")
        assert slip.status == "pending_finance_review"

    def test_contract_terminate_api_does_not_create_cash_flow(self, mock_check, auth_client):
        employee = EmployeeFactory(employment_status="active")
        contract = EmploymentContractFactory(employee=employee, status="active")
        url = f"/api/v1/hrm/contracts/{contract.id}/terminate/"
        data = {
            "termination_date": "2026-06-15",
            "reason": "Nghi viec theo nguyen vong",
        }

        from apps.finance.models import CashFlowTransaction

        initial_count = CashFlowTransaction.objects.count()
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert CashFlowTransaction.objects.count() == initial_count

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
        assert response.data["count"] >= 2
        assert "employee_code" in response.data["results"][0]
        assert "employee_name" in response.data["results"][0]

    def test_list_disciplines(self, mock_check, auth_client):
        employee = EmployeeFactory()
        DisciplineRecordFactory.create_batch(2, employee=employee)
        url = "/api/v1/hrm/disciplines/"
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 2
        assert "employee_code" in response.data["results"][0]
        assert "employee_name" in response.data["results"][0]

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

    def test_contract_renew_api(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, EmploymentContractFactory

        employee = EmployeeFactory()
        contract = EmploymentContractFactory(
            employee=employee,
            contract_no="CON-EXP-API",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            status="active",
        )

        url = f"/api/v1/hrm/contracts/{contract.id}/renew/"
        data = {
            "new_contract_no": "CON-EXP-API-RENEW",
            "new_contract_type": "definite_term",
            "start_date": "2026-06-01",
            "new_salary_base": "12000000.00",
            "note": "Gia hạn hợp đồng mẫu",
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == 201
        assert response.data["contract"] is not None
        assert response.data["contract"]["contract_no"] == "CON-EXP-API-RENEW"
        assert Decimal(response.data["contract"]["salary_base"]) == Decimal("12000000.00")

    def test_partial_salary_slip_create_api(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory

        employee = EmployeeFactory()
        url = "/api/v1/hrm/salary-slips/partial/"
        data = {
            "employee_id": str(employee.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-15",
            "name": "SALARY-API-PARTIAL",
        }
        response = auth_client.post(url, data, format="json")

        assert response.status_code == 201
        assert response.data["status"] == "draft"
        assert response.data["breakdown"]["is_partial"] is True

    def test_payroll_submit_and_recall_api(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, SalarySlipFactory

        employee = EmployeeFactory()
        slip = SalarySlipFactory(employee=employee, salary_period="2026-06", status="calculated")

        # Submit
        submit_url = f"/api/v1/hrm/salary-slips/{slip.id}/submit-for-review/"
        response = auth_client.post(submit_url)
        assert response.status_code == 200
        assert response.data["status"] == "pending_finance_review"

        # Recall (should return 404 now that route is deleted)
        recall_url = f"/api/v1/hrm/salary-slips/{slip.id}/recall/"
        response = auth_client.post(recall_url)
        assert response.status_code == 404

    def test_salary_slip_bulk_calculate_api(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, EmploymentContractFactory, SalarySlipFactory

        employee1 = EmployeeFactory(salary_base__create_contract=False)
        employee2 = EmployeeFactory(salary_base__create_contract=False)

        EmploymentContractFactory(
            employee=employee1,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            status="active",
            salary_base=Decimal("10000000.00"),
        )
        EmploymentContractFactory(
            employee=employee2,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            status="active",
            salary_base=Decimal("12000000.00"),
        )

        SalarySlipFactory(employee=employee1, salary_period="2026-06", status="draft")
        SalarySlipFactory(employee=employee2, salary_period="2026-06", status="draft")

        url = "/api/v1/hrm/salary-slips/bulk-calculate/"
        data = {"salary_period": "2026-06"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_salary_slip_bulk_submit_api(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, SalarySlipFactory

        employee1 = EmployeeFactory()
        employee2 = EmployeeFactory()

        SalarySlipFactory(employee=employee1, salary_period="2026-06", status="calculated")
        SalarySlipFactory(employee=employee2, salary_period="2026-06", status="calculated")

        url = "/api/v1/hrm/salary-slips/bulk-submit-for-review/"
        data = {"salary_period": "2026-06"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == 200
        assert response.data["count"] == 2


@pytest.mark.django_db
@patch("apps.common.xlib.permissions.PermissionChecker.check_permission", return_value=True)
class TestRewardDisciplineCRUDAPI:
    def test_reward_detail_get_success(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, RewardRecordFactory

        employee = EmployeeFactory()
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            reward_type="performance_bonus",
            amount=Decimal("1000000.00"),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/rewards/{reward.id}/"
        response = auth_client.get(url)

        assert response.status_code == 200
        assert response.data["id"] == str(reward.id)
        assert response.data["status"] == "pending_approval"

    def test_reward_detail_patch_success(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, RewardRecordFactory

        employee = EmployeeFactory()
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            reward_type="performance_bonus",
            amount=Decimal("1000000.00"),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/rewards/{reward.id}/"
        data = {"amount": 1500000, "description": "New description via API"}
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == 200
        assert response.data["amount"] == "1500000.00"
        assert response.data["description"] == "New description via API"

    def test_reward_detail_delete_success(self, mock_check, auth_client):
        from apps.hrm.models import RewardRecord
        from apps.hrm.tests.factories import EmployeeFactory, RewardRecordFactory

        employee = EmployeeFactory()
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/rewards/{reward.id}/"
        response = auth_client.delete(url)

        assert response.status_code == 204
        assert not RewardRecord.objects.filter(id=reward.id).exists()

    def test_reward_detail_delete_blocked_when_approved(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, RewardRecordFactory

        employee = EmployeeFactory()
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="approved",
        )

        url = f"/api/v1/hrm/rewards/{reward.id}/"
        response = auth_client.delete(url)

        assert response.status_code == 400
        assert "Chỉ có thể xóa khen thưởng ở trạng thái chờ duyệt" in response.data["error"]

    def test_reward_cancel_post_success(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, RewardRecordFactory

        employee = EmployeeFactory()
        reward = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 10),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/rewards/{reward.id}/cancel/"
        data = {"reason": "Not correct"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == 200
        assert response.data["status"] == "cancelled"

    def test_reward_list_with_filters(self, mock_check, auth_client):
        from apps.hrm.tests.factories import EmployeeFactory, RewardRecordFactory

        employee1 = EmployeeFactory()
        employee2 = EmployeeFactory()

        RewardRecordFactory(
            employee=employee1,
            reward_date=date(2026, 6, 10),
            reward_type="performance_bonus",
            status="approved",
        )
        RewardRecordFactory(
            employee=employee2,
            reward_date=date(2026, 6, 11),
            reward_type="initiative",
            status="pending_approval",
        )

        url = "/api/v1/hrm/rewards/"
        response = auth_client.get(url, {"status": "approved"})

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["status"] == "approved"

        # Check date range filter
        response = auth_client.get(url, {"date_from": "2026-06-11", "date_to": "2026-06-12"})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["reward_date"] == "2026-06-11"

    def test_discipline_detail_get_success(self, mock_check, auth_client):
        from apps.hrm.tests.factories import DisciplineRecordFactory, EmployeeFactory

        employee = EmployeeFactory()
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            discipline_type="warning",
            status="pending_approval",
        )

        url = f"/api/v1/hrm/disciplines/{discipline.id}/"
        response = auth_client.get(url)

        assert response.status_code == 200
        assert response.data["id"] == str(discipline.id)

    def test_discipline_detail_patch_success(self, mock_check, auth_client):
        from apps.hrm.tests.factories import DisciplineRecordFactory, EmployeeFactory

        employee = EmployeeFactory()
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            discipline_type="warning",
            status="pending_approval",
        )

        url = f"/api/v1/hrm/disciplines/{discipline.id}/"
        data = {"description": "New description via API for discipline"}
        response = auth_client.patch(url, data, format="json")

        assert response.status_code == 200
        assert response.data["description"] == "New description via API for discipline"

    def test_discipline_detail_delete_success(self, mock_check, auth_client):
        from apps.hrm.models import DisciplineRecord
        from apps.hrm.tests.factories import DisciplineRecordFactory, EmployeeFactory

        employee = EmployeeFactory()
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/disciplines/{discipline.id}/"
        response = auth_client.delete(url)

        assert response.status_code == 204
        assert not DisciplineRecord.objects.filter(id=discipline.id).exists()

    def test_discipline_cancel_post_success(self, mock_check, auth_client):
        from apps.hrm.tests.factories import DisciplineRecordFactory, EmployeeFactory

        employee = EmployeeFactory()
        discipline = DisciplineRecordFactory(
            employee=employee,
            incident_date=date(2026, 6, 10),
            discipline_date=date(2026, 6, 12),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/disciplines/{discipline.id}/cancel/"
        data = {"reason": "Not correct violation"}
        response = auth_client.post(url, data, format="json")

        assert response.status_code == 200
        assert response.data["status"] == "cancelled"

    def test_discipline_approve_termination_api_success(self, mock_check, auth_client):
        from apps.hrm.tests.factories import DisciplineRecordFactory, EmployeeFactory, EmploymentContractFactory
        from apps.master_data.models import Employee

        employee = EmployeeFactory(
            employee_id="NV_API_1", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-API-1", status="active")
        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/disciplines/{discipline.id}/approve/"
        response = auth_client.post(url)

        assert response.status_code == 200
        assert response.data["status"] == "approved"

        employee.refresh_from_db()
        contract.refresh_from_db()
        assert employee.employment_status == "inactive"
        assert contract.status == "terminated"

    def test_discipline_approve_termination_api_returns_400_on_contract_error(self, mock_check, auth_client):
        from apps.hrm.tests.factories import (
            DisciplineRecordFactory,
            EmployeeFactory,
            EmploymentContractFactory,
            SalarySlipFactory,
        )

        employee = EmployeeFactory(
            employee_id="NV_API_2", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-API-2", status="active")

        SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        discipline = DisciplineRecordFactory(
            employee=employee,
            discipline_type="termination",
            discipline_date=date(2026, 6, 15),
            incident_date=date(2026, 6, 14),
            status="pending_approval",
        )

        url = f"/api/v1/hrm/disciplines/{discipline.id}/approve/"
        response = auth_client.post(url)

        assert response.status_code == 400
        assert "vẫn còn nợ lương kỳ trước chưa thanh toán" in str(response.data)
