from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.hashers import check_password

from apps.accounts.models import SystemLog, User
from apps.hrm.models import (
    Attendance,
    DisciplineRecord,
    EmployeeDocument,
    EmploymentContract,
    EmploymentHistory,
    LeaveRequest,
    RewardRecord,
)
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
from apps.hrm.tests.factories import (
    AttendanceFactory,
    DisciplineRecordFactory,
    EmployeeFactory,
    EmploymentContractFactory,
    EmploymentHistoryFactory,
    LeaveRequestFactory,
    RewardRecordFactory,
    SalarySlipFactory,
)
from apps.inventory.tests.factories import RoleFactory, UserFactory
from apps.master_data.models import Employee


@pytest.fixture(autouse=True)
def mock_check_permission():
    with patch("apps.common.xlib.permissions.PermissionChecker.check_permission") as mock:
        mock.return_value = True
        yield mock


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


@pytest.mark.django_db
class TestContractServices:

    def test_contract_create_first_contract(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP0001", full_name="John Doe")
        admin = UserFactory(username="admin_creator")
        contract_data = {
            "contract_no": "HDLD-2026-0001",
            "contract_type": "definite_term",
            "start_date": date(2026, 1, 1),
            "end_date": date(2026, 12, 31),
            "note": "Hợp đồng lao động năm 2026",
            "file_url": "https://example.com/scan_contract.pdf",
        }

        # Act
        contract = contract_create_or_renew(employee_id=employee.id, contract_data=contract_data, creator=admin)

        # Assert
        assert contract is not None
        assert contract.contract_no == "HDLD-2026-0001"
        assert contract.status == "active"
        assert contract.employee == employee

        # Verify EmployeeDocument was created for the scan
        doc = EmployeeDocument.objects.filter(employee=employee, doc_type="contract_scan").first()
        assert doc is not None
        assert doc.file_url == "https://example.com/scan_contract.pdf"
        assert doc.uploaded_by == admin

        # Verify SystemLog for contract creation
        log = SystemLog.objects.filter(table_name="employment_contract", record_id=str(contract.id), user=admin).first()
        assert log is not None
        assert log.action == "create"

    def test_contract_renew_expires_old_contract(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP0002", full_name="Jane Doe")
        admin = UserFactory(username="admin_creator")
        old_contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-OLD", status="active")

        new_contract_data = {
            "contract_no": "HDLD-NEW",
            "contract_type": "indefinite_term",
            "start_date": date(2027, 1, 1),
            "note": "Gia hạn hợp đồng vô thời hạn",
        }

        # Act
        new_contract = contract_create_or_renew(employee_id=employee.id, contract_data=new_contract_data, creator=admin)

        # Assert
        # Refresh old contract from DB
        old_contract.refresh_from_db()
        assert old_contract.status == "expired"
        assert new_contract.contract_no == "HDLD-NEW"
        assert new_contract.status == "active"

        # Verify SystemLogs for both old contract update (to expired) and new contract create
        old_log = SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(old_contract.id), action="update", user=admin
        ).first()
        assert old_log is not None
        assert old_log.new_value["status"] == "expired"

        new_log = SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(new_contract.id), action="create", user=admin
        ).first()
        assert new_log is not None

    def test_contract_terminate_disables_user_and_employee(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP0003", full_name="Bob Smith", employment_status="active")
        # Create an associated user
        user = UserFactory(username="bobsmith", employee_id="EMP0003", is_active=True)
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-BOB", status="active")
        admin = UserFactory(username="admin_creator")

        # Act
        terminated_contract = contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 6, 30),
            reason="Sa thải do vi phạm kỷ luật",
            terminator=admin,
            file_url="https://example.com/quyet_dinh_thoi_viec.pdf",
        )

        # Assert
        terminated_contract.refresh_from_db()
        employee.refresh_from_db()
        user.refresh_from_db()

        assert terminated_contract.status == "terminated"
        assert terminated_contract.end_date == date(2026, 6, 30)
        assert employee.employment_status == "inactive"
        assert employee.leave_date == date(2026, 6, 30)
        assert user.is_active is False

        # Verify Document was created
        doc = EmployeeDocument.objects.filter(employee=employee, doc_type="resignation_letter").first()
        assert doc is not None
        assert doc.file_url == "https://example.com/quyet_dinh_thoi_viec.pdf"

        # Verify Logs
        contract_log = SystemLog.objects.filter(
            table_name="employment_contract", record_id=str(contract.id), action="update", user=admin
        ).first()
        assert contract_log is not None
        assert contract_log.new_value["status"] == "terminated"

        employee_log = SystemLog.objects.filter(
            table_name="employee", record_id=str(employee.id), action="update", user=admin
        ).first()
        assert employee_log is not None
        assert employee_log.new_value["employment_status"] == "inactive"

        user_log = SystemLog.objects.filter(
            table_name="user", record_id=str(user.id), action="update", user=admin
        ).first()
        assert user_log is not None
        assert user_log.new_value["is_active"] is False


@pytest.mark.django_db
class TestEmploymentHistoryServices:

    def test_update_salary_creates_history_and_logs(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP1111", salary_base=Decimal("10000000.00"))
        admin = UserFactory(username="admin_history")
        change_data = {
            "change_type": "salary_change",
            "new_salary_base": Decimal("13000000.00"),
            "effective_date": date(2026, 6, 1),
            "reason": "Điều chỉnh lương cơ bản theo hiệu suất",
        }

        # Act
        updated_employee = employee_update_salary_or_title(
            employee_id=employee.id, change_data=change_data, approved_by_user_id=admin.id
        )

        # Assert
        updated_employee.refresh_from_db()
        assert updated_employee.salary_base == Decimal("13000000.00")

        # Verify EmploymentHistory was created
        history = EmploymentHistory.objects.filter(employee=employee).first()
        assert history is not None
        assert history.change_type == "salary_change"
        assert history.old_salary_base == Decimal("10000000.00")
        assert history.new_salary_base == Decimal("13000000.00")
        assert history.effective_date == date(2026, 6, 1)
        assert history.approved_by == admin
        assert history.reason == "Điều chỉnh lương cơ bản theo hiệu suất"

        # Verify SystemLog was written
        log = SystemLog.objects.filter(table_name="employment_history", record_id=str(history.id), user=admin).first()
        assert log is not None
        assert log.action == "create"
        assert Decimal(str(log.new_value["new_salary_base"])) == Decimal("13000000.00")

    def test_update_title_creates_history_and_logs(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP2222", position_title="Junior Developer")
        admin = UserFactory(username="admin_history_2")
        change_data = {
            "change_type": "title_change",
            "new_title": "Senior Developer",
            "effective_date": date(2026, 6, 1),
            "reason": "Thăng chức sau kỳ đánh giá",
        }

        # Act
        updated_employee = employee_update_salary_or_title(
            employee_id=employee.id, change_data=change_data, approved_by_user_id=admin.id
        )

        # Assert
        updated_employee.refresh_from_db()
        assert updated_employee.position_title == "Senior Developer"

        # Verify EmploymentHistory
        history = EmploymentHistory.objects.filter(employee=employee).first()
        assert history is not None
        assert history.change_type == "title_change"
        assert history.old_title == "Junior Developer"
        assert history.new_title == "Senior Developer"
        assert history.effective_date == date(2026, 6, 1)

        # Verify SystemLog
        log = SystemLog.objects.filter(table_name="employment_history", record_id=str(history.id), user=admin).first()
        assert log is not None

    def test_update_department_creates_history_and_logs(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP3333", department="IT")
        admin = UserFactory(username="admin_history_3")
        change_data = {
            "change_type": "department_transfer",
            "new_department": "R&D",
            "effective_date": date(2026, 6, 1),
            "reason": "Điều chuyển nhân sự dự án mới",
        }

        # Act
        updated_employee = employee_update_salary_or_title(
            employee_id=employee.id, change_data=change_data, approved_by_user_id=admin.id
        )

        # Assert
        updated_employee.refresh_from_db()
        assert updated_employee.department == "R&D"

        # Verify EmploymentHistory
        history = EmploymentHistory.objects.filter(employee=employee).first()
        assert history is not None
        assert history.change_type == "department_transfer"
        assert history.old_department == "IT"
        assert history.new_department == "R&D"

        # Verify SystemLog
        log = SystemLog.objects.filter(table_name="employment_history", record_id=str(history.id), user=admin).first()
        assert log is not None


@pytest.mark.django_db
class TestAttendanceAndLeaveServices:

    def test_attendance_batch_record_creates_and_updates(self):
        # Arrange
        employee1 = EmployeeFactory(employee_id="EMP5001")
        employee2 = EmployeeFactory(employee_id="EMP5002")
        admin = UserFactory(username="admin_attendance")
        attendance_date = date(2026, 5, 20)

        # Tạo trước một bản ghi cho employee1 để test update
        AttendanceFactory(employee=employee1, date=attendance_date, status="working", work_hours=Decimal("8.00"))

        records = [
            {
                "employee_id": str(employee1.id),
                "status": "working",
                "work_hours": Decimal("4.00"),  # cập nhật từ 8 xuống 4
                "overtime_hours": Decimal("2.00"),
                "remarks": "Đi làm nửa ngày, OT 2h",
            },
            {
                "employee_id": str(employee2.id),
                "status": "paid_leave",
                "work_hours": Decimal("0.00"),  # tạo mới
                "overtime_hours": Decimal("0.00"),
                "remarks": "Nghỉ phép năm",
            },
        ]

        # Act
        created_records = attendance_batch_record(date=attendance_date, records=records, creator=admin)

        # Assert
        assert len(created_records) == 2

        # Verify employee1 update
        att1 = Attendance.objects.get(employee=employee1, date=attendance_date)
        assert att1.work_hours == Decimal("4.00")
        assert att1.overtime_hours == Decimal("2.00")
        assert att1.remarks == "Đi làm nửa ngày, OT 2h"

        # Verify employee2 create
        att2 = Attendance.objects.get(employee=employee2, date=attendance_date)
        assert att2.status == "paid_leave"
        assert att2.work_hours == Decimal("0.00")

        # Verify logs
        log1 = SystemLog.objects.filter(
            table_name="attendance", record_id=str(att1.id), action="update", user=admin
        ).first()
        assert log1 is not None
        assert Decimal(str(log1.new_value["work_hours"])) == Decimal("4.00")

        log2 = SystemLog.objects.filter(
            table_name="attendance", record_id=str(att2.id), action="create", user=admin
        ).first()
        assert log2 is not None
        assert log2.new_value["status"] == "paid_leave"

    def test_leave_request_workflow(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP6001")
        admin = UserFactory(username="admin_leave")
        leave_data = {
            "leave_type": "paid",
            "start_date": date(2026, 5, 10),
            "end_date": date(2026, 5, 12),
            "days": Decimal("3.0"),
            "reason": "Nghỉ phép năm đi du lịch",
        }

        # Act 1: Create leave request
        request = leave_request_create(employee_id=employee.id, data=leave_data)

        # Assert 1
        assert request is not None
        assert request.status == "pending"
        assert request.employee == employee
        assert request.leave_type == "paid"

        # Verify log for create
        create_log = SystemLog.objects.filter(
            table_name="leave_request", record_id=str(request.id), action="create"
        ).first()
        assert create_log is not None
        assert create_log.new_value["leave_type"] == "paid"

        # Act 2: Approve leave request
        approved_request = leave_request_approve(leave_request_id=request.id, approved_by_user_id=admin.id)

        # Assert 2
        approved_request.refresh_from_db()
        assert approved_request.status == "approved"
        assert approved_request.approved_by == admin
        assert approved_request.approved_at is not None

        # Verify logs for approve
        approve_log = SystemLog.objects.filter(
            table_name="leave_request", record_id=str(request.id), action="update", user=admin
        ).first()
        assert approve_log is not None
        assert approve_log.new_value["status"] == "approved"

        # Verify that Attendance records were auto-created for 2026-05-10, 2026-05-11, 2026-05-12
        dates_to_check = [date(2026, 5, 10), date(2026, 5, 11), date(2026, 5, 12)]
        for d in dates_to_check:
            att = Attendance.objects.filter(employee=employee, date=d).first()
            assert att is not None
            assert att.status == "paid_leave"  # "paid" leave_type maps to "paid_leave" attendance status
            assert att.work_hours == Decimal("0.00")
            assert att.overtime_hours == Decimal("0.00")

            # Check attendance logs
            att_log = SystemLog.objects.filter(table_name="attendance", record_id=str(att.id), action="create").first()
            assert att_log is not None
            assert att_log.new_value["status"] == "paid_leave"

    def test_leave_request_create_without_reason(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP6002")
        leave_data = {
            "leave_type": "unpaid",
            "start_date": date(2026, 5, 15),
            "end_date": date(2026, 5, 15),
            "days": Decimal("1.0"),
            "reason": "",  # Empty reason
        }

        # Act
        request = leave_request_create(employee_id=employee.id, data=leave_data)

        # Assert
        assert request is not None
        assert request.status == "pending"
        assert request.reason == "" or request.reason is None


@pytest.mark.django_db
class TestPayrollAndRewardDisciplineServices:

    def test_reward_record_create(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP7001")
        admin = UserFactory(username="admin_reward")
        data = {
            "reward_date": date(2026, 5, 15),
            "reward_type": "performance_bonus",
            "amount": Decimal("1500000.00"),
            "description": "Thành tích xuất sắc trong dự án",
        }

        # Act
        reward = reward_record_create(employee_id=employee.id, data=data, creator=admin)

        # Assert
        assert reward is not None
        assert reward.employee == employee
        assert reward.amount == Decimal("1500000.00")
        assert reward.reward_type == "performance_bonus"

        # Verify log
        log = SystemLog.objects.filter(table_name="reward_record", record_id=str(reward.id), user=admin).first()
        assert log is not None
        assert log.action == "create"
        assert Decimal(str(log.new_value["amount"])) == Decimal("1500000.00")

    def test_discipline_record_create(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP7002")
        admin = UserFactory(username="admin_discipline")
        data = {
            "incident_date": date(2026, 5, 10),
            "discipline_date": date(2026, 5, 12),
            "discipline_type": "salary_deduction",
            "penalty_amount": Decimal("500000.00"),
            "description": "Vi phạm quy chế bảo mật thông tin",
            "file_url": "https://example.com/scan_incident.pdf",
        }

        # Act
        discipline = discipline_record_create(employee_id=employee.id, data=data, creator=admin)

        # Assert
        assert discipline is not None
        assert discipline.employee == employee
        assert discipline.penalty_amount == Decimal("500000.00")
        assert discipline.file_url == "https://example.com/scan_incident.pdf"

        # Verify log
        log = SystemLog.objects.filter(table_name="discipline_record", record_id=str(discipline.id), user=admin).first()
        assert log is not None
        assert log.action == "create"

    def test_payroll_initialize_period(self):
        # Arrange
        EmployeeFactory(employee_id="EMP7003", employment_status="active")
        EmployeeFactory(employee_id="EMP7004", employment_status="active")
        EmployeeFactory(employee_id="EMP7005", employment_status="inactive")
        admin = UserFactory(username="admin_payroll")

        # Act
        slips = payroll_initialize_period(salary_period="2026-05", creator=admin)

        # Assert
        # 2 active employees should get slips, inactive employee shouldn't
        assert len(slips) == 2
        employee_ids = [slip.employee.employee_id for slip in slips]
        assert "EMP7003" in employee_ids
        assert "EMP7004" in employee_ids
        assert "EMP7005" not in employee_ids

        # Slips should be in draft status
        for slip in slips:
            assert slip.status == "draft"
            assert slip.salary_period == "2026-05"

            # Check log
            log = SystemLog.objects.filter(table_name="salary_slip", record_id=str(slip.id), user=admin).first()
            assert log is not None
            assert log.action == "create"

    def test_payroll_initialize_period_already_exists(self):
        # Arrange
        from apps.common.xlib.exceptions import ValidationException

        employee = EmployeeFactory(employee_id="EMP7003", employment_status="active")
        admin = UserFactory(username="admin_payroll")

        # Khởi tạo trước một phiếu lương để kỳ lương này xem như đã tồn tại
        SalarySlipFactory(employee=employee, salary_period="2026-05", status="draft")

        # Act & Assert
        with pytest.raises(ValidationException) as excinfo:
            payroll_initialize_period(salary_period="2026-05", creator=admin)

        assert "Kỳ lương đã được khởi tạo trước đó." in str(excinfo.value)

    def test_payroll_calculate_salary_with_all_components(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP7006",
            salary_base=Decimal("13000000.00"),
            is_union_member=True,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll")

        # 1. Chấm công trong tháng 5/2026:
        # Giả sử tháng 5 có 26 ngày công chuẩn.
        # Nhân viên đi làm 20 ngày "working" (8h/ngày, không OT).
        # Nghỉ phép 2 ngày "paid_leave" (8h/ngày, work_hours=0).
        # Nghỉ phép 2 ngày "unpaid_leave" (work_hours=0).
        # Có 2 ngày làm thêm: 1 ngày làm thêm 4h, 1 ngày làm thêm 6h (Tổng 10h overtime).
        # Cấu hình cụ thể:
        for day in range(1, 21):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        for day in range(21, 23):
            AttendanceFactory(
                employee=employee, date=date(2026, 5, day), status="paid_leave", work_hours=Decimal("0.00")
            )

        for day in range(23, 25):
            AttendanceFactory(
                employee=employee, date=date(2026, 5, day), status="unpaid_leave", work_hours=Decimal("0.00")
            )

        # Thêm OT vào 2 ngày đi làm
        att_ot1 = Attendance.objects.get(employee=employee, date=date(2026, 5, 1))
        att_ot1.overtime_hours = Decimal("4.00")
        att_ot1.save()

        att_ot2 = Attendance.objects.get(employee=employee, date=date(2026, 5, 2))
        att_ot2.overtime_hours = Decimal("6.00")
        att_ot2.save()

        # 2. Thưởng & Phạt:
        # Tạo 1 phiếu thưởng 1.500.000 VNĐ
        reward = RewardRecordFactory(employee=employee, reward_date=date(2026, 5, 15), amount=Decimal("1500000.00"))

        # Tạo 1 phiếu kỷ luật phạt 500.000 VNĐ
        discipline = DisciplineRecordFactory(
            employee=employee, discipline_date=date(2026, 5, 12), penalty_amount=Decimal("500000.00")
        )

        # Khởi tạo salary slip
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        reward.refresh_from_db()
        discipline.refresh_from_db()

        # Kiểm tra liên kết thưởng/phạt với phiếu lương
        assert reward.salary_slip == calculated_slip
        assert discipline.salary_slip == calculated_slip

        assert calculated_slip.base_salary == Decimal("11000000.00")
        assert calculated_slip.overtime_amount == Decimal("937500.00")
        assert calculated_slip.reward_amount_total == Decimal("1500000.00")
        assert calculated_slip.discipline_deduction_total == Decimal("500000.00")
        assert calculated_slip.union_fee_2pct == Decimal("260000.00")
        assert calculated_slip.gross_pay == Decimal("11937500.00")
        assert calculated_slip.deductions == Decimal("760000.00")
        assert calculated_slip.net_pay == Decimal("12677500.00")

    def test_payroll_cash_payment_warning(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP7007",
            salary_base=Decimal("12000000.00"),
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll")

        # Đi làm đủ 26 ngày
        for day in range(1, 27):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", payment_method="cash")

        # Act
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        assert calculated_slip.net_pay == Decimal("12000000.00")
        # Do trả tiền mặt từ 5 triệu trở lên, phải ghi nhận cảnh báo trong remarks
        assert calculated_slip.remarks is not None
        assert "cảnh báo" in calculated_slip.remarks.lower() or "tiền mặt" in calculated_slip.remarks.lower()

    def test_payroll_initialize_period_uses_employee_salary_base(self):
        # Arrange
        EmployeeFactory(employee_id="EMP9001", salary_base=Decimal("15000000.00"), employment_status="active")
        admin = UserFactory(username="admin_test_1")

        # Act
        slips = payroll_initialize_period(salary_period="2026-05", creator=admin)

        # Assert
        assert len(slips) == 1
        assert slips[0].base_salary == Decimal("15000000.00")

    def test_payroll_bulk_confirm_and_pay(self):
        from apps.finance.models import CashFlowTransaction, SalarySlip

        # Arrange
        emp1 = EmployeeFactory(employee_id="EMP9501", full_name="Emp 1")
        emp2 = EmployeeFactory(employee_id="EMP9502", full_name="Emp 2")
        admin = UserFactory(username="admin_payroll")

        # Khởi tạo 2 phiếu lương của kỳ 2026-05 dạng draft (sửa thành approved để test confirm & pay)
        slip1 = SalarySlipFactory(
            employee=emp1,
            salary_period="2026-05",
            base_salary=Decimal("5000000.00"),
            net_pay=Decimal("5000000.00"),
            status="approved",
        )
        slip2 = SalarySlipFactory(
            employee=emp2,
            salary_period="2026-05",
            base_salary=Decimal("6000000.00"),
            net_pay=Decimal("6000000.00"),
            status="approved",
        )

        # Phiếu lương của kỳ khác (không bị ảnh hưởng)
        slip_other = SalarySlipFactory(
            employee=emp1,
            salary_period="2026-04",
            net_pay=Decimal("4500000.00"),
            status="draft",
        )

        # Act
        from apps.hrm.services import payroll_bulk_confirm_and_pay

        updated_slips = payroll_bulk_confirm_and_pay(
            salary_period="2026-05", payment_method="bank_transfer", creator=admin
        )

        # Assert
        assert len(updated_slips) == 2

        # Refresh from DB
        slip1.refresh_from_db()
        slip2.refresh_from_db()
        slip_other.refresh_from_db()

        assert slip1.status == "paid"
        assert slip1.payment_method == "bank_transfer"
        assert slip2.status == "paid"
        assert slip2.payment_method == "bank_transfer"
        assert slip_other.status == "draft"  # Remains draft

        # Verify CashFlowTransactions
        tx1 = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP9501-2026-05").first()
        tx2 = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP9502-2026-05").first()

        assert tx1 is not None
        assert tx1.amount == Decimal("5000000.00")
        assert tx2 is not None
        assert tx2.amount == Decimal("6000000.00")

        # Verify SystemLogs
        slip_logs = SystemLog.objects.filter(table_name="salary_slip", action="update", user=admin)
        assert slip_logs.count() == 2

        tx_logs = SystemLog.objects.filter(table_name="cash_flow_transaction", action="create", user=admin)
        assert tx_logs.count() == 2

    def test_payroll_bulk_confirm_and_pay_handles_zero_and_negative_net_pay(self):
        from apps.finance.models import CashFlowTransaction, SalarySlip

        # Arrange
        emp1 = EmployeeFactory(employee_id="EMP9503", full_name="Emp 3")  # Lương dương -> pay
        emp2 = EmployeeFactory(employee_id="EMP9504", full_name="Emp 4")  # Lương bằng 0 -> bỏ qua
        emp3 = EmployeeFactory(employee_id="EMP9505", full_name="Emp 5")  # Lương âm -> receive
        admin = UserFactory(username="admin_payroll_neg")

        slip_positive = SalarySlipFactory(
            employee=emp1,
            salary_period="2026-05",
            base_salary=Decimal("5000000.00"),
            net_pay=Decimal("5000000.00"),
            status="approved",
        )
        slip_zero = SalarySlipFactory(
            employee=emp2,
            salary_period="2026-05",
            base_salary=Decimal("0.00"),
            net_pay=Decimal("0.00"),
            status="approved",
        )
        slip_negative = SalarySlipFactory(
            employee=emp3,
            salary_period="2026-05",
            base_salary=Decimal("1000000.00"),
            net_pay=Decimal("-200000.00"),
            status="approved",
        )

        # Act
        from apps.hrm.services import payroll_bulk_confirm_and_pay

        updated_slips = payroll_bulk_confirm_and_pay(
            salary_period="2026-05", payment_method="bank_transfer", creator=admin
        )

        # Assert
        assert len(updated_slips) == 3

        # Refresh from DB
        slip_positive.refresh_from_db()
        slip_zero.refresh_from_db()
        slip_negative.refresh_from_db()

        assert slip_positive.status == "paid"
        assert slip_zero.status == "paid"
        assert slip_negative.status == "paid"

        # Verify CashFlowTransactions
        tx_pos = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP9503-2026-05").first()
        tx_zero = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP9504-2026-05").first()
        tx_neg = CashFlowTransaction.objects.filter(name="PAY-SALARY-EMP9505-2026-05").first()

        # Tiền dương -> pay
        assert tx_pos is not None
        assert tx_pos.payment_type == "pay"
        assert tx_pos.amount == Decimal("5000000.00")

        # Tiền bằng 0 -> bỏ qua không tạo transaction
        assert tx_zero is None

        # Tiền âm -> receive với trị tuyệt đối abs(amount)
        assert tx_neg is not None
        assert tx_neg.payment_type == "receive"
        assert tx_neg.amount == Decimal("200000.00")

    def test_payroll_calculate_salary_with_late_reward_and_discipline(self):
        from apps.finance.models import SalarySlip
        from apps.hrm.models import DisciplineRecord, RewardRecord

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP9999",
            salary_base=Decimal("10000000.00"),
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll")

        # 1. Tạo và xác nhận thanh toán phiếu lương Kỳ 05/2026 cho nhân viên (để giả lập kỳ này đã paid)
        slip_may = SalarySlipFactory(
            employee=employee,
            salary_period="2026-05",
            base_salary=Decimal("10000000.00"),
            net_pay=Decimal("10000000.00"),
            status="paid",
        )

        # 2. Tạo Khen thưởng và Kỷ luật có ngày quyết định trong tháng 5 (Kỳ 05) sau khi đã chi lương tháng 5
        # Do tạo sau khi đã chi lương, salary_slip của các bản ghi này sẽ là None
        reward_late = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 5, 20),
            amount=Decimal("1500000.00"),
            salary_slip=None,
        )
        discipline_late = DisciplineRecordFactory(
            employee=employee,
            discipline_date=date(2026, 5, 22),
            penalty_amount=Decimal("500000.00"),
            salary_slip=None,
        )

        # 3. Khởi tạo phiếu lương Kỳ 06/2026
        slip_june = SalarySlipFactory(
            employee=employee,
            salary_period="2026-06",
            base_salary=Decimal("10000000.00"),
            status="draft",
        )

        # Act
        # Chạy tính toán lương cho Kỳ tháng 6 (26 ngày công chuẩn, đi làm đủ ngày)
        for day in range(1, 27):
            AttendanceFactory(employee=employee, date=date(2026, 6, day), status="working", work_hours=Decimal("8.00"))

        calculated_slip = payroll_calculate_salary(salary_slip_id=slip_june.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        reward_late.refresh_from_db()
        discipline_late.refresh_from_db()

        # Kiểm tra xem các bản ghi thưởng/phạt muộn của tháng 5 KHÔNG được gán vào phiếu lương tháng 6
        assert reward_late.salary_slip is None
        assert discipline_late.salary_slip is None

        # Kiểm tra các giá trị trên phiếu lương tháng 6:
        # Lương thực tế: 10,000,000 * 26 / 26 = 10,000,000
        # Thưởng: 0 (vì đã lọc theo start_date tháng 6)
        # Khấu trừ/Kỷ luật: 0 (vì đã lọc theo start_date tháng 6)
        # Thực nhận = 10,000,000
        assert calculated_slip.reward_amount_total == Decimal("0.00")
        assert calculated_slip.discipline_deduction_total == Decimal("0.00")
        assert calculated_slip.gross_pay == Decimal("10000000.00")
        assert calculated_slip.deductions == Decimal("0.00")
        assert calculated_slip.net_pay == Decimal("10000000.00")

    def test_payroll_calculate_salary_with_rewards_within_period(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP9998",
            salary_base=Decimal("10000000.00"),
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_within")

        # 1. Tạo Khen thưởng và Kỷ luật có ngày quyết định trong tháng 6 (Kỳ 06)
        reward_within = RewardRecordFactory(
            employee=employee,
            reward_date=date(2026, 6, 15),
            amount=Decimal("1200000.00"),
            salary_slip=None,
        )
        discipline_within = DisciplineRecordFactory(
            employee=employee,
            discipline_date=date(2026, 6, 20),
            penalty_amount=Decimal("300000.00"),
            salary_slip=None,
        )

        # 2. Khởi tạo phiếu lương Kỳ 06/2026
        slip_june = SalarySlipFactory(
            employee=employee,
            salary_period="2026-06",
            base_salary=Decimal("10000000.00"),
            status="draft",
        )

        # Act
        for day in range(1, 27):
            AttendanceFactory(employee=employee, date=date(2026, 6, day), status="working", work_hours=Decimal("8.00"))

        calculated_slip = payroll_calculate_salary(salary_slip_id=slip_june.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        reward_within.refresh_from_db()
        discipline_within.refresh_from_db()

        # Thưởng/kỷ luật phát sinh trong kỳ phải được liên kết và tính toán
        assert reward_within.salary_slip == calculated_slip
        assert discipline_within.salary_slip == calculated_slip
        assert calculated_slip.reward_amount_total == Decimal("1200000.00")
        assert calculated_slip.discipline_deduction_total == Decimal("300000.00")
        assert calculated_slip.net_pay == Decimal("10900000.00")

    def test_contract_terminate_fails_if_previous_payroll_unpaid(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP9002", salary_base=Decimal("12000000.00"), employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-9002", status="active")
        admin = UserFactory(username="admin_test_2")

        # Tạo slip kỳ trước chưa thanh toán (status != 'paid')
        SalarySlipFactory(employee=employee, salary_period="2026-04", status="draft")

        # Act & Assert
        from apps.common.xlib.exceptions import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            contract_terminate(
                contract_id=contract.id,
                termination_date=date(2026, 5, 15),
                reason="Thôi việc",
                terminator=admin,
                is_lawful=True,
            )
        assert "vẫn còn nợ lương kỳ trước chưa thanh toán" in str(exc_info.value)

    def test_contract_terminate_lawful_resignation_with_bhxh(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP9003", salary_base=Decimal("13000000.00"), employment_status="active", is_union_member=False
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-9003", status="active")
        admin = UserFactory(username="admin_test_3")

        # Chấm công trong tháng 5/2026 từ ngày 1 đến 15 (15 ngày công thực tế)
        for day in range(1, 16):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        # Act
        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 15),
            reason="Thôi việc đúng luật",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("2.5"),
            standard_working_days=26,
        )

        # Assert
        employee.refresh_from_db()
        assert employee.employment_status == "inactive"
        assert employee.leave_date == date(2026, 5, 15)

        # Kiểm tra phiếu lương kỳ này được quyết toán và chuyển sang paid
        from apps.finance.models import CashFlowTransaction, SalarySlip

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "paid"

        # 15 ngày công trên 26 ngày chuẩn: 13,000,000 * 15 / 26 = 7,500,000
        assert slip.base_salary == Decimal("7500000.00")

        # Tiền phép năm: 13,000,000 / 26 * 2.5 = 1,250,000
        # BHXH (làm 15 ngày >= 14 ngày nên phải đóng): 13,000,000 * 10.5% = 1,365,000
        # Gross = 7,500,000 + 1,250,000 = 8,750,000
        # Deductions = 1,365,000
        # Net = Gross - Deductions = 7,385,000
        assert slip.gross_pay == Decimal("8750000.00")
        assert slip.deductions == Decimal("1365000.00")
        assert slip.net_pay == Decimal("7385000.00")

        # Kiểm tra bút toán chi tiền lương
        tx = CashFlowTransaction.objects.filter(name=f"PAY-FINAL-SALARY-{employee.employee_id}-2026-05").first()
        assert tx is not None
        assert tx.amount == Decimal("7385000.00")

    def test_contract_terminate_unlawful_resignation_without_bhxh(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP9004", salary_base=Decimal("26000000.00"), employment_status="active", is_union_member=False
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-9004", status="active")
        admin = UserFactory(username="admin_test_4")

        # Chấm công trong tháng 5/2026 từ ngày 1 đến 10 (10 ngày công thực tế)
        for day in range(1, 11):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        # Act
        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 10),
            reason="Nghỉ ngang không báo trước",
            terminator=admin,
            is_lawful=False,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
            unnotified_days=30,
        )

        # Assert
        from apps.finance.models import CashFlowTransaction, SalarySlip

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "paid"

        # 10 ngày công trên 26 ngày chuẩn: 26,000,000 * 10 / 26 = 10,000,000
        assert slip.base_salary == Decimal("10000000.00")

        # Tiền phép năm: 0
        # BHXH (làm 10 ngày < 14 ngày nên không phải đóng): 0
        # Phạt nghỉ ngang:
        #   - Phạt nửa tháng lương: 26,000,000 * 0.5 = 13,000,000
        #   - Bồi thường 30 ngày không báo trước: 26,000,000 / 26 * 30 = 30,000,000
        #   - Tổng phạt = 43,000,000
        # Gross = 10,000,000
        # Deductions = 43,000,000
        # Net = Gross - Deductions = -33,000,000 (NLĐ nợ ngược công ty)
        assert slip.gross_pay == Decimal("10000000.00")
        assert slip.deductions == Decimal("43000000.00")
        assert slip.net_pay == Decimal("-33000000.00")

        # Assert CashFlowTransaction
        tx = CashFlowTransaction.objects.filter(name=f"COLLECT-FINAL-SALARY-{employee.employee_id}-2026-05").first()
        assert tx is not None
        assert tx.payment_type == "receive"
        assert tx.category == "Thu hồi bồi thường nhân viên thôi việc"
        assert tx.amount == Decimal("33000000.00")


@pytest.mark.django_db
class TestHrmPermissionAndBypass:

    def test_leave_request_approve_fails_if_approver_does_not_exist(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP9988")
        leave_request = LeaveRequestFactory(employee=employee, status="pending")

        # Act & Assert
        from apps.common.xlib.exceptions import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            leave_request_approve(
                leave_request_id=leave_request.id,
                approved_by_user_id="00000000-0000-0000-0000-000000000000",  # Random non-existent UUID
            )
        assert "Người phê duyệt không tồn tại" in str(exc_info.value)

    def test_leave_request_approve_fails_if_no_permission(self, mock_check_permission):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP9987")
        leave_request = LeaveRequestFactory(employee=employee, status="pending")
        approver = UserFactory(username="no_permission_approver")

        # Mock check_permission raise PermissionException
        from apps.common.xlib.exceptions import PermissionException

        mock_check_permission.side_effect = PermissionException("Người dùng không có quyền: hrm.change_leaverequest")

        # Act & Assert
        with pytest.raises(PermissionException) as exc_info:
            leave_request_approve(
                leave_request_id=leave_request.id,
                approved_by_user_id=str(approver.id),
            )
        assert "không có quyền: hrm.change_leaverequest" in str(exc_info.value)

    def test_employee_update_salary_or_title_fails_if_approver_does_not_exist(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP9986")
        change_data = {
            "change_type": "salary_change",
            "new_salary_base": Decimal("13000000.00"),
            "effective_date": date(2026, 6, 1),
            "reason": "Tăng lương",
        }

        # Act & Assert
        from apps.common.xlib.exceptions import ValidationException

        with pytest.raises(ValidationException) as exc_info:
            employee_update_salary_or_title(
                employee_id=employee.id,
                change_data=change_data,
                approved_by_user_id="00000000-0000-0000-0000-000000000000",
            )
        assert "Người phê duyệt không tồn tại" in str(exc_info.value)

    def test_employee_update_salary_or_title_fails_if_no_permission(self, mock_check_permission):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP9985")
        approver = UserFactory(username="no_permission_approver_2")
        change_data = {
            "change_type": "salary_change",
            "new_salary_base": Decimal("13000000.00"),
            "effective_date": date(2026, 6, 1),
            "reason": "Tăng lương",
        }

        # Mock check_permission raise PermissionException
        from apps.common.xlib.exceptions import PermissionException

        mock_check_permission.side_effect = PermissionException("Người dùng không có quyền: hrm.change_employee")

        # Act & Assert
        with pytest.raises(PermissionException) as exc_info:
            employee_update_salary_or_title(
                employee_id=employee.id,
                change_data=change_data,
                approved_by_user_id=str(approver.id),
            )
        assert "không có quyền: hrm.change_employee" in str(exc_info.value)

    def test_payroll_calculate_salary_with_public_holiday(self):
        from apps.hrm.models import PublicHoliday

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8800",
            salary_base=Decimal("13000000.00"),
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll")

        # Create a public holiday in 2026-05
        PublicHoliday.objects.create(name="Tết Đoan Ngọ", start_date=date(2026, 5, 5), days=1)

        # Initialize slip
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act 1: Calculate salary without any attendance records
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert 1: Employee should receive 1.0 paid leave day dynamically from the public holiday
        calculated_slip.refresh_from_db()
        # 1 day of base salary = 13,000,000 / 26 * 1 = 500,000
        assert calculated_slip.base_salary == Decimal("500000.00")
        assert calculated_slip.net_pay == Decimal("500000.00")

        # Act 2: Add working attendance on the public holiday
        AttendanceFactory(employee=employee, date=date(2026, 5, 5), status="working", work_hours=Decimal("8.00"))

        # Calculate again
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)
        calculated_slip.refresh_from_db()

        # Assert 2: They have a working record, so they get 1 day of base salary (no double credit for holiday)
        assert calculated_slip.base_salary == Decimal("500000.00")

    def test_payroll_calculate_salary_with_multi_day_public_holiday(self):
        from apps.hrm.models import PublicHoliday

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8801",
            salary_base=Decimal("13000000.00"),
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_multi")

        # Create a 3-day public holiday in 2026-05 (May 1st, 2nd, 3rd)
        PublicHoliday.objects.create(name="Đại Lễ 30/4-1/5", start_date=date(2026, 5, 1), days=3)

        # Initialize slip
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act: Calculate salary without any attendance records
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert: Employee should receive 4.0 paid leave days dynamically from the multi-day public holiday (including compensatory day)
        calculated_slip.refresh_from_db()
        # 4 days of base salary = 13,000,000 / 26 * 4 = 2,000,000
        assert calculated_slip.base_salary == Decimal("2000000.00")
        assert calculated_slip.net_pay == Decimal("2000000.00")

    def test_payroll_calculate_salary_with_spanning_public_holiday(self):
        from apps.hrm.models import PublicHoliday

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8802",
            salary_base=Decimal("13000000.00"),
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_spanning")

        # Create a 3-day public holiday starting on last day of April (April 30th) spanning into May
        # April 30, May 1, May 2
        PublicHoliday.objects.create(name="Ngày Lễ Kéo Dài", start_date=date(2026, 4, 30), days=3)

        # Initialize slip for May (2026-05)
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act: Calculate salary without any attendance records
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert: Employee should receive 2.0 paid leave days (May 1st & May 2nd) dynamically from the public holiday
        calculated_slip.refresh_from_db()
        # 2 days of base salary = 13,000,000 / 26 * 2 = 1,000,000
        assert calculated_slip.base_salary == Decimal("1000000.00")
        assert calculated_slip.net_pay == Decimal("1000000.00")

    def test_payroll_calculate_salary_with_different_ot_rates(self):
        from apps.hrm.models import PublicHoliday

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8803",
            salary_base=Decimal("10400000.00"),  # 400.000 / day, 50.000 / hour
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_ot")

        # Create a public holiday in 2026-05
        PublicHoliday.objects.create(name="Ngày Chiến thắng", start_date=date(2026, 5, 1), days=1)

        # Chấm công
        # May 1st (Holiday): đi làm 8h OT
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 1),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("8.00"),
        )
        # May 3rd (Sunday): đi làm 4h OT
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 3),
            status="working",
            work_hours=Decimal("0.00"),
            overtime_hours=Decimal("4.00"),
        )
        # May 4th (Weekday): đi làm 8h, OT 2h
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 4),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("2.00"),
        )

        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()

        # May 1 (working) -> +1 day. May 4 (working) -> +1 day. Total = 2 working days.
        # Base salary earned = 10,400,000 * 2 / 26 = 800,000
        assert calculated_slip.base_salary == Decimal("800000.00")

        # Overtime:
        # Normal OT: 2 hours * 50,000 * 1.5 = 150,000
        # Weekend OT: 4 hours * 50,000 * 2.0 = 400,000
        # Holiday OT: 8 hours * 50,000 * 3.0 = 1,200,000
        # Total OT Amount = 1,750,000
        assert calculated_slip.overtime_amount == Decimal("1750000.00")
        assert calculated_slip.net_pay == Decimal("2550000.00")

        # Check breakdown
        incomes = calculated_slip.breakdown["incomes"]
        normal_ot_entry = next((inc for inc in incomes if "ngày thường" in inc["name"]), None)
        weekend_ot_entry = next((inc for inc in incomes if "Chủ nhật" in inc["name"]), None)
        holiday_ot_entry = next((inc for inc in incomes if "ngày Lễ/Tết" in inc["name"]), None)

        assert normal_ot_entry is not None
        assert normal_ot_entry["amount"] == 150000.0
        assert weekend_ot_entry is not None
        assert weekend_ot_entry["amount"] == 400000.0
        assert holiday_ot_entry is not None
        assert holiday_ot_entry["amount"] == 1200000.0

    def test_contract_terminate_with_overtime_rates(self):
        from apps.hrm.models import PublicHoliday

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8804",
            salary_base=Decimal("10400000.00"),  # 400.000 / day
            is_union_member=False,
            employment_status="active",
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-8804", status="active")
        admin = UserFactory(username="admin_payroll_term")

        # Create a public holiday in 2026-05
        PublicHoliday.objects.create(name="Ngày Chiến thắng", start_date=date(2026, 5, 1), days=1)

        # Chấm công từ ngày 1 đến 5 (May 1st: holiday 8h OT, May 3rd: Sunday 4h OT, May 4th: weekday 8h work + 2h OT, May 5th: weekday 8h work)
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 1),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("8.00"),
        )
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 3),
            status="working",
            work_hours=Decimal("0.00"),
            overtime_hours=Decimal("4.00"),
        )
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 4),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("2.00"),
        )
        AttendanceFactory(employee=employee, date=date(2026, 5, 5), status="working", work_hours=Decimal("8.00"))

        # Act
        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 5),
            reason="Thôi việc đúng luật",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
        )

        # Assert
        from apps.finance.models import SalarySlip

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "paid"

        # Overtime calculation:
        # Normal OT: 2 hours * 50,000 * 1.5 = 150,000
        # Weekend OT: 4 hours * 50,000 * 2.0 = 400,000
        # Holiday OT: 8 hours * 50,000 * 3.0 = 1,200,000
        # Total OT Amount = 1,750,000
        assert slip.overtime_amount == Decimal("1750000.00")

        incomes = slip.breakdown["incomes"]
        normal_ot_entry = next((inc for inc in incomes if "ngày thường" in inc["name"]), None)
        weekend_ot_entry = next((inc for inc in incomes if "Chủ nhật" in inc["name"]), None)
        holiday_ot_entry = next((inc for inc in incomes if "ngày Lễ/Tết" in inc["name"]), None)

        assert normal_ot_entry is not None
        assert normal_ot_entry["amount"] == 150000.0
        assert weekend_ot_entry is not None
        assert weekend_ot_entry["amount"] == 400000.0
        assert holiday_ot_entry is not None
        assert holiday_ot_entry["amount"] == 1200000.0

    def test_payroll_calculate_salary_with_simplified_statuses(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8809",
            salary_base=Decimal("13000000.00"),
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_simple")

        # Chấm công trong tháng 5/2026: 24 ngày working, 2 ngày paid_leave
        for day in range(1, 25):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))
        for day in range(25, 27):
            AttendanceFactory(
                employee=employee, date=date(2026, 5, day), status="paid_leave", work_hours=Decimal("0.00")
            )

        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        # 24 working + 2 paid_leave = 26 standard days. Base salary earned = 13,000,000 * 26 / 26 = 13,000,000
        assert calculated_slip.base_salary == Decimal("13000000.00")
        assert calculated_slip.net_pay == Decimal("13000000.00")

    def test_leave_request_approve_sync_attendance(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP8810", employment_status="active")
        approver = UserFactory(username="approver_sync_test")

        # Pending leave request for 1 day: 2026-05-18, type 'paid'
        leave_request = LeaveRequestFactory(
            employee=employee,
            leave_type="paid",
            start_date=date(2026, 5, 18),
            end_date=date(2026, 5, 18),
            days=Decimal("1.0"),
            status="pending",
        )

        # Act 1: Approve leave request
        approved_request = leave_request_approve(
            leave_request_id=leave_request.id,
            approved_by_user_id=str(approver.id),
        )

        # Assert 1: Leave request approved, attendance synchronized to paid_leave
        assert approved_request.status == "approved"
        attendance = Attendance.objects.filter(employee=employee, date=date(2026, 5, 18)).first()
        assert attendance is not None
        assert attendance.status == "paid_leave"
        assert attendance.work_hours == Decimal("0.00")

        # Act 2: Employee goes to work on 2026-05-18 despite leave approval, update attendance to 'working'
        attendance.status = "working"
        attendance.work_hours = Decimal("8.00")
        attendance.save()

        # Assert 2: Attendance record is updated correctly
        attendance.refresh_from_db()
        assert attendance.status == "working"
        assert attendance.work_hours == Decimal("8.00")


@pytest.mark.django_db
class TestHrmCompensatoryHolidayRules:

    def test_compensatory_holiday_overlap_sunday(self):
        from apps.hrm.models import PublicHoliday
        from apps.hrm.services import get_holiday_dates_for_period

        # May 3rd, 2026 is a Sunday
        PublicHoliday.objects.create(name="Lễ Trùng Chủ Nhật", start_date=date(2026, 5, 3), days=1)

        official, compensatory = get_holiday_dates_for_period(2026, 5)

        assert date(2026, 5, 3) in official
        assert date(2026, 5, 4) in compensatory
        assert len(official) == 1
        assert len(compensatory) == 1

    def test_holiday_on_saturday_no_compensation(self):
        from apps.hrm.models import PublicHoliday
        from apps.hrm.services import get_holiday_dates_for_period

        # May 2nd, 2026 is a Saturday
        PublicHoliday.objects.create(name="Lễ Thứ Bảy", start_date=date(2026, 5, 2), days=1)

        official, compensatory = get_holiday_dates_for_period(2026, 5)

        assert date(2026, 5, 2) in official
        assert len(compensatory) == 0

    def test_compensatory_holiday_multi_day_block_ends_tuesday(self):
        from apps.hrm.models import PublicHoliday
        from apps.hrm.services import get_holiday_dates_for_period

        # May 2nd (Saturday) to May 5th (Tuesday) - May 3rd is Sunday
        PublicHoliday.objects.create(name="Lễ Dài Ngày", start_date=date(2026, 5, 2), days=4)

        official, compensatory = get_holiday_dates_for_period(2026, 5)

        assert date(2026, 5, 2) in official
        assert date(2026, 5, 3) in official
        assert date(2026, 5, 4) in official
        assert date(2026, 5, 5) in official
        assert date(2026, 5, 6) in compensatory  # Wednesday May 6th is compensatory day
        assert len(official) == 4
        assert len(compensatory) == 1

    def test_working_on_compensatory_holiday_rate(self):
        from apps.hrm.models import PublicHoliday

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8805",
            salary_base=Decimal("10400000.00"),  # 400.000 / day, 50.000 / hour
            is_union_member=False,
            employment_status="active",
        )
        admin = UserFactory(username="admin_comp_ot")

        # May 3rd, 2026 is Sunday, May 4th is compensatory holiday
        PublicHoliday.objects.create(name="Lễ Chủ Nhật", start_date=date(2026, 5, 3), days=1)

        # Chấm công làm việc 8 tiếng và làm thêm 4 tiếng vào ngày nghỉ bù thứ Hai 4/5
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 4),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("4.00"),
        )

        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        # 1 working day (4/5) + 1 credited holiday day (3/5) = 2 days
        # Base salary = 10,400,000 * 2 / 26 = 800,000
        assert calculated_slip.base_salary == Decimal("800000.00")

        # Overtime on compensatory day: 4 hours * 50,000 * 2.0 (compensatory OT rate) = 400,000
        assert calculated_slip.overtime_amount == Decimal("400000.00")

        incomes = calculated_slip.breakdown["incomes"]
        comp_ot_entry = next((inc for inc in incomes if "ngày nghỉ bù" in inc["name"]), None)
        assert comp_ot_entry is not None
        assert comp_ot_entry["amount"] == 400000.0

    def test_contract_terminate_with_compensatory_holidays(self):
        from apps.hrm.models import PublicHoliday

        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8806",
            salary_base=Decimal("10400000.00"),  # 400.000 / day, 50.000 / hour
            is_union_member=False,
            employment_status="active",
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-8806", status="active")
        admin = UserFactory(username="admin_comp_term")

        # May 3rd, 2026 is Sunday, May 4th is compensatory holiday
        PublicHoliday.objects.create(name="Lễ Chủ Nhật", start_date=date(2026, 5, 3), days=1)

        # Chấm công làm việc vào ngày nghỉ bù thứ Hai 4/5
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 4),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("4.00"),
        )
        # Thôi việc vào ngày 5/5
        AttendanceFactory(employee=employee, date=date(2026, 5, 5), status="working", work_hours=Decimal("8.00"))

        # Act
        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 5),
            reason="Thôi việc đúng luật",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
        )

        # Assert
        from apps.finance.models import SalarySlip

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "paid"

        # Days worked/credited:
        # May 3 (holiday) -> credited 1.0 day
        # May 4 (worked) -> 1.0 day
        # May 5 (worked) -> 1.0 day
        # Total = 3 days. Base salary earned = 10,400,000 * 3 / 26 = 1,200,000
        assert slip.base_salary == Decimal("1200000.00")

        # Overtime on compensatory day: 4 hours * 50,000 * 2.0 = 400,000
        assert slip.overtime_amount == Decimal("400000.00")

        incomes = slip.breakdown["incomes"]
        comp_ot_entry = next((inc for inc in incomes if "ngày nghỉ bù" in inc["name"]), None)
        assert comp_ot_entry is not None
        assert comp_ot_entry["amount"] == 400000.0
        assert slip.breakdown["standard_working_days"] == 26


@pytest.mark.django_db
class TestPayrollPeriodConstraintsAndEmployeeProtection:

    def test_attendance_batch_record_blocked_when_period_paid(self):
        from apps.common.xlib.exceptions import ValidationException

        # Arrange
        employee = EmployeeFactory(employee_id="EMP_CONSTRAINT_1", employment_status="active")
        admin = UserFactory(username="admin_constraint_1")

        # Create a paid salary slip for 2026-05
        SalarySlipFactory(employee=employee, salary_period="2026-05", status="paid")

        # Act & Assert
        records = [{"employee_id": str(employee.id), "status": "working", "work_hours": Decimal("8.00")}]
        with pytest.raises(ValidationException) as exc_info:
            attendance_batch_record(date=date(2026, 5, 15), records=records, creator=admin)

        assert "Kỳ lương 2026-05 đã được thanh toán 100%" in str(exc_info.value)

    def test_leave_request_approve_blocked_when_period_paid(self):
        from apps.common.xlib.exceptions import ValidationException

        # Arrange
        employee = EmployeeFactory(employee_id="EMP_CONSTRAINT_2", employment_status="active")
        admin = UserFactory(username="admin_constraint_2")

        # Create a paid salary slip for 2026-05
        SalarySlipFactory(employee=employee, salary_period="2026-05", status="paid")

        # Create a pending leave request spanning 2026-05-10 to 2026-05-12
        leave_data = {
            "leave_type": "paid",
            "start_date": date(2026, 5, 10),
            "end_date": date(2026, 5, 12),
            "days": Decimal("3.0"),
            "reason": "Nghỉ phép",
        }
        request = leave_request_create(employee_id=employee.id, data=leave_data)

        # Act & Assert
        with pytest.raises(ValidationException) as exc_info:
            leave_request_approve(leave_request_id=request.id, approved_by_user_id=admin.id)

        assert "Kỳ lương 2026-05 đã được thanh toán 100%" in str(exc_info.value)

    def test_employee_deletion_blocked_by_protected_records(self):
        from django.db.models.deletion import ProtectedError

        # Arrange
        employee = EmployeeFactory(employee_id="EMP_CONSTRAINT_3", employment_status="active")

        # Create a related record, e.g. Attendance
        AttendanceFactory(employee=employee, date=date(2026, 5, 15), status="working")

        # Act & Assert
        with pytest.raises(ProtectedError):
            employee.delete()
