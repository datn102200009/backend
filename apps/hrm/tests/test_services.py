from datetime import date
from decimal import Decimal

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
    payroll_confirm_and_pay,
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
            "leave_type": "sick",
            "start_date": date(2026, 5, 10),
            "end_date": date(2026, 5, 12),
            "days": Decimal("3.0"),
            "reason": "Nghỉ ốm nằm viện",
        }

        # Act 1: Create leave request
        request = leave_request_create(employee_id=employee.id, data=leave_data)

        # Assert 1
        assert request is not None
        assert request.status == "pending"
        assert request.employee == employee
        assert request.leave_type == "sick"

        # Verify log for create
        create_log = SystemLog.objects.filter(
            table_name="leave_request", record_id=str(request.id), action="create"
        ).first()
        assert create_log is not None
        assert create_log.new_value["leave_type"] == "sick"

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
            assert att.status == "sick_leave"  # "sick" leave_type maps to "sick_leave" attendance status
            assert att.work_hours == Decimal("0.00")
            assert att.overtime_hours == Decimal("0.00")

            # Check attendance logs
            att_log = SystemLog.objects.filter(table_name="attendance", record_id=str(att.id), action="create").first()
            assert att_log is not None
            assert att_log.new_value["status"] == "sick_leave"


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
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, standard_days=26, creator=admin)

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
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, standard_days=26, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        assert calculated_slip.net_pay == Decimal("12000000.00")
        # Do trả tiền mặt từ 5 triệu trở lên, phải ghi nhận cảnh báo trong remarks
        assert calculated_slip.remarks is not None
        assert "cảnh báo" in calculated_slip.remarks.lower() or "tiền mặt" in calculated_slip.remarks.lower()

    def test_payroll_confirm_and_pay_creates_cash_flow_transaction(self):
        from apps.finance.models import CashFlowTransaction

        # Arrange
        employee = EmployeeFactory(employee_id="EMP7008", full_name="Nguyen Van Finance")
        admin = UserFactory(username="admin_payroll")

        # Tạo sẵn slip đã được tính toán lương
        slip = SalarySlipFactory(
            employee=employee,
            salary_period="2026-05",
            base_salary=Decimal("8000000.00"),
            gross_pay=Decimal("8000000.00"),
            deductions=Decimal("0.00"),
            net_pay=Decimal("8000000.00"),
            payment_method="bank_transfer",
            status="draft",
        )

        # Act
        paid_slip = payroll_confirm_and_pay(salary_slip_id=slip.id, creator=admin)

        # Assert
        paid_slip.refresh_from_db()
        assert paid_slip.status == "paid"

        # Verify that CashFlowTransaction was created
        tx = CashFlowTransaction.objects.filter(payment_type="pay", amount=Decimal("8000000.00")).first()
        assert tx is not None
        assert tx.category == "Chi trả lương nhân viên"
        assert "Nguyen Van Finance" in tx.remarks
        assert "2026-05" in tx.remarks
