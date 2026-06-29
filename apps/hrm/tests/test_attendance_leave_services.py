from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.accounts.models import SystemLog
from apps.hrm.models import Attendance
from apps.hrm.services import attendance_batch_record, leave_request_approve, leave_request_create
from apps.hrm.tests.factories import AttendanceFactory, EmployeeFactory, LeaveRequestFactory
from apps.inventory.tests.factories import UserFactory


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

    def test_leave_request_approve_overwrites_working_attendance_with_warning(self):
        # Arrange
        employee = EmployeeFactory(employee_id="EMP8811", employment_status="active")
        approver = UserFactory(username="approver_warning_test")

        # Pre-create a working attendance record
        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 20),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("2.00"),
            remarks="Giờ làm thực tế",
        )

        # Create a pending leave request overlapping with that day
        leave_request = LeaveRequestFactory(
            employee=employee,
            leave_type="unpaid",
            start_date=date(2026, 5, 20),
            end_date=date(2026, 5, 20),
            days=Decimal("1.0"),
            status="pending",
        )

        # Act
        with patch("apps.hrm.services.logger") as mock_logger:
            approved_request = leave_request_approve(
                leave_request_id=leave_request.id,
                approved_by_user_id=str(approver.id),
            )

        # Assert
        assert approved_request.status == "approved"
        attendance = Attendance.objects.filter(employee=employee, date=date(2026, 5, 20)).first()
        assert attendance is not None
        assert attendance.status == "unpaid_leave"
        assert attendance.work_hours == Decimal("0.00")
        assert attendance.overtime_hours == Decimal("0.00")

        # Verify logger warning was called
        mock_logger.warning.assert_called_once()
        assert "Overwriting working attendance" in mock_logger.warning.call_args[0][0]
