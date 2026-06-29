from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.accounts.models import SystemLog, User
from apps.common.xlib.exceptions import ValidationException
from apps.finance.models import CashFlowTransaction, SalarySlip
from apps.hrm.models import Attendance, DisciplineRecord, PublicHoliday, RewardRecord
from apps.hrm.services import (
    _calc_termination_compensation,
    attendance_batch_record,
    contract_terminate,
    create_partial_salary_slip,
    leave_request_approve,
    leave_request_create,
    payroll_bulk_calculate,
    payroll_bulk_submit_for_review,
    payroll_calculate_salary,
    payroll_calculate_terminated_salary,
    payroll_initialize_period,
    payroll_submit_for_review,
)
from apps.hrm.tests.factories import (
    AttendanceFactory,
    DisciplineRecordFactory,
    EmployeeFactory,
    EmploymentContractFactory,
    RewardRecordFactory,
    SalarySlipFactory,
)
from apps.inventory.tests.factories import UserFactory


@pytest.mark.django_db
class TestPayrollServices:

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

        # Slips should be in calculated status
        for slip in slips:
            assert slip.status == "calculated"
            assert slip.salary_period == "2026-05"

            # Check log
            log = (
                SystemLog.objects.filter(table_name="salary_slip", record_id=str(slip.id), user=admin)
                .order_by("created_at")
                .first()
            )
            assert log is not None
            assert log.action == "create"

    def test_payroll_initialize_period_already_exists(self):
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
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll")

        # 1. Chấm công trong tháng 5/2026:
        # Giả sử tháng 5 có 26 ngày công chuẩn.
        # Nhân viên đi làm 20 ngày "working" (8h/ngày, không OT).
        # Nghỉ phép 2 ngày "paid_leave" (8h/ngày, work_hours=0).
        # Nghỉ phép 2 ngày "unpaid_leave" (work_hours=0).
        # Có 2 ngày làm thêm: 1 ngày làm thêm 4h, 1 ngày làm thêm 6h (Tổng 10h overtime).
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
        reward = RewardRecordFactory(employee=employee, reward_date=date(2026, 5, 15), amount=Decimal("1500000.00"))
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
        assert calculated_slip.gross_pay == Decimal("11937500.00")
        assert calculated_slip.deductions == Decimal("500000.00")
        assert calculated_slip.net_pay == Decimal("12937500.00")

    def test_payroll_cash_payment_warning(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP7007",
            salary_base=Decimal("12000000.00"),
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
        assert calculated_slip.remarks is not None
        assert "cảnh báo" in calculated_slip.remarks.lower() or "tiền mặt" in calculated_slip.remarks.lower()

    def test_payroll_initialize_period_sets_zero_base_salary(self):
        # Arrange
        EmployeeFactory(employee_id="EMP9001", salary_base=Decimal("15000000.00"), employment_status="active")
        admin = UserFactory(username="admin_test_1")

        # Act
        slips = payroll_initialize_period(salary_period="2026-05", creator=admin)

        # Assert
        assert len(slips) == 1
        assert slips[0].base_salary == Decimal("0.00")

    def test_payroll_calculate_salary_with_late_reward_and_discipline(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP9999",
            salary_base=Decimal("10000000.00"),
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll")

        # 1. Tạo và xác nhận thanh toán phiếu lương Kỳ 05/2026
        SalarySlipFactory(
            employee=employee,
            salary_period="2026-05",
            base_salary=Decimal("10000000.00"),
            net_pay=Decimal("10000000.00"),
            status="paid",
        )

        # 2. Tạo Khen thưởng và Kỷ luật muộn có ngày quyết định trong tháng 5 (Kỳ 05) sau khi đã chi lương tháng 5
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

        # Kiểm tra các giá trị trên phiếu lương tháng 6
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
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_within")

        # 1. Tạo Khen thưởng và Kỷ luật trong tháng 6 (Kỳ 06)
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

        # Tạo slip kỳ trước chưa thanh toán
        SalarySlipFactory(employee=employee, salary_period="2026-04", status="draft")

        # Act & Assert
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
        employee = EmployeeFactory(employee_id="NV9003", salary_base__create_contract=False, employment_status="active")
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-9003", status="active", salary_base=Decimal("13000000.00")
        )
        admin = UserFactory(username="admin_test_3")

        # Chấm công trong tháng 5/2026 từ ngày 1 đến 15 (15 ngày công)
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

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "pending_finance_review"

        # 15 ngày công trên 26 ngày chuẩn: 13,000,000 * 15 / 26 = 7,500,000
        assert slip.base_salary == Decimal("7500000.00")

        # Tiền phép năm: 13,000,000 / 26 * 2.5 = 1,250,000
        # BHXH (làm 15 ngày >= 14 ngày nên phải đóng): 13,000,000 * 10.5% = 1,365,000
        assert slip.gross_pay == Decimal("8750000.00")
        assert slip.deductions == Decimal("1365000.00")
        assert slip.net_pay == Decimal("7385000.00")

        # Kiểm tra bút toán chi tiền lương không được tự động tạo ở HRM nữa
        tx = CashFlowTransaction.objects.filter(name=f"PAY-FINAL-SALARY-{employee.employee_id}-2026-05").first()
        assert tx is None

    def test_contract_terminate_unlawful_resignation_without_bhxh(self):
        # Arrange
        employee = EmployeeFactory(employee_id="NV9004", salary_base__create_contract=False, employment_status="active")
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-9004", status="active", salary_base=Decimal("26000000.00")
        )
        admin = UserFactory(username="admin_test_4")

        # Chấm công trong tháng 5/2026 từ ngày 1 đến 10 (10 ngày công)
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
        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "pending_finance_review"

        # 10 ngày công trên 26 ngày chuẩn: 26,000,000 * 10 / 26 = 10,000,000
        assert slip.base_salary == Decimal("10000000.00")

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

        tx = CashFlowTransaction.objects.filter(name=f"COLLECT-FINAL-SALARY-{employee.employee_id}-2026-05").first()
        assert tx is None

    def test_payroll_calculate_salary_with_public_holiday(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8800",
            salary_base=Decimal("13000000.00"),
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
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8801",
            salary_base=Decimal("13000000.00"),
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
        assert calculated_slip.base_salary == Decimal("2000000.00")
        assert calculated_slip.net_pay == Decimal("2000000.00")

    def test_payroll_calculate_salary_with_spanning_public_holiday(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8802",
            salary_base=Decimal("13000000.00"),
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_spanning")

        # Create a 3-day public holiday starting on last day of April (April 30th) spanning into May
        PublicHoliday.objects.create(name="Ngày Lễ Kéo Dài", start_date=date(2026, 4, 30), days=3)

        # Initialize slip for May (2026-05)
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act: Calculate salary without any attendance records
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert: Employee should receive 2.0 paid leave days (May 1st & May 2nd) dynamically from the public holiday
        calculated_slip.refresh_from_db()
        assert calculated_slip.base_salary == Decimal("1000000.00")
        assert calculated_slip.net_pay == Decimal("1000000.00")

    def test_payroll_calculate_salary_with_different_ot_rates(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8803",
            salary_base=Decimal("10400000.00"),  # 400.000 / day, 50.000 / hour
            employment_status="active",
        )
        admin = UserFactory(username="admin_payroll_ot")

        # Create a public holiday in 2026-05
        PublicHoliday.objects.create(name="Ngày Chiến thắng", start_date=date(2026, 5, 1), days=1)

        # Chấm công
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

        slip = SalarySlipFactory(employee=employee, salary_period="2026-05")

        # Act
        calculated_slip = payroll_calculate_salary(salary_slip_id=slip.id, creator=admin)

        # Assert
        calculated_slip.refresh_from_db()
        assert calculated_slip.base_salary == Decimal("800000.00")
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
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8804",
            salary_base=Decimal("10400000.00"),  # 400.000 / day
            employment_status="active",
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-8804", status="active")
        admin = UserFactory(username="admin_payroll_term")

        # Create a public holiday in 2026-05
        PublicHoliday.objects.create(name="Ngày Chiến thắng", start_date=date(2026, 5, 1), days=1)

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
        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "pending_finance_review"
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
        assert calculated_slip.base_salary == Decimal("13000000.00")
        assert calculated_slip.net_pay == Decimal("13000000.00")

    def test_salary_timeline_no_change(self):
        from apps.hrm.selectors import get_salary_timeline

        employee = EmployeeFactory(
            employee_id="EMP_TIMELINE_1", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        period_start = date(2026, 6, 1)
        period_end = date(2026, 6, 30)

        # Act
        timeline = get_salary_timeline(employee, period_start, period_end)

        # Assert
        assert len(timeline) == 1
        assert timeline[0] == (period_start, Decimal("10000000.00"))

    def test_salary_timeline_single_change_mid_month(self):
        from apps.hrm.selectors import get_salary_timeline

        employee = EmployeeFactory(
            employee_id="NV_TIMELINE_2", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        # Update default contract to end on June 15
        default_contract = employee.contracts.first()
        default_contract.end_date = date(2026, 6, 15)
        default_contract.save()

        # Create renewed contract starting June 16
        EmploymentContractFactory(
            employee=employee,
            contract_no="HDLD-NV-TIMELINE-2-NEW",
            start_date=date(2026, 6, 16),
            end_date=date(2026, 12, 31),
            status="active",
            salary_base=Decimal("12000000.00"),
        )
        period_start = date(2026, 6, 1)
        period_end = date(2026, 6, 30)

        # Act
        timeline = get_salary_timeline(employee, period_start, period_end)

        # Assert
        assert len(timeline) == 2
        assert timeline[0] == (period_start, Decimal("10000000.00"))
        assert timeline[1] == (date(2026, 6, 16), Decimal("12000000.00"))

    def test_salary_timeline_multiple_changes_in_period(self):
        from apps.hrm.selectors import get_salary_timeline, split_into_segments

        employee = EmployeeFactory(
            employee_id="NV_TIMELINE_3", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        default_contract = employee.contracts.first()
        default_contract.end_date = date(2026, 6, 9)
        default_contract.save()

        EmploymentContractFactory(
            employee=employee,
            contract_no="HDLD-TIMELINE-3-C2",
            start_date=date(2026, 6, 10),
            end_date=date(2026, 6, 19),
            status="active",
            salary_base=Decimal("12000000.00"),
        )
        EmploymentContractFactory(
            employee=employee,
            contract_no="HDLD-TIMELINE-3-C3",
            start_date=date(2026, 6, 20),
            end_date=date(2026, 12, 31),
            status="active",
            salary_base=Decimal("15000000.00"),
        )
        period_start = date(2026, 6, 1)
        period_end = date(2026, 6, 30)

        # Act
        timeline = get_salary_timeline(employee, period_start, period_end)
        segments = split_into_segments(timeline, period_start, period_end)

        # Assert
        assert len(timeline) == 3
        assert timeline[0] == (period_start, Decimal("10000000.00"))
        assert timeline[1] == (date(2026, 6, 10), Decimal("12000000.00"))
        assert timeline[2] == (date(2026, 6, 20), Decimal("15000000.00"))

        assert len(segments) == 3
        assert segments[0] == (date(2026, 6, 1), date(2026, 6, 9), Decimal("10000000.00"))
        assert segments[1] == (date(2026, 6, 10), date(2026, 6, 19), Decimal("12000000.00"))
        assert segments[2] == (date(2026, 6, 20), date(2026, 6, 30), Decimal("15000000.00"))

    def test_breakdown_contains_salary_segments(self):
        employee = EmployeeFactory(
            employee_id="NV_SEG_1", salary_base__create_contract=False, employment_status="active"
        )
        EmploymentContractFactory(
            employee=employee,
            contract_no="HDLD-SEG-1",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 15),
            status="active",
            salary_base=Decimal("10000000.00"),
        )
        EmploymentContractFactory(
            employee=employee,
            contract_no="HDLD-SEG-2",
            start_date=date(2026, 6, 16),
            end_date=date(2026, 12, 31),
            status="active",
            salary_base=Decimal("12000000.00"),
        )

        admin = UserFactory(username="admin_seg_test")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-06", status="draft")

        for d in range(1, 31):
            day = date(2026, 6, d)
            if day.weekday() not in [5, 6]:
                AttendanceFactory(employee=employee, date=day, status="working", work_hours=Decimal("8.00"))

        # Act
        calculated_slip = payroll_calculate_salary(salary_slip_id=str(slip.id), creator=admin)

        # Assert
        assert calculated_slip.status == "calculated"
        assert "salary_segments" in calculated_slip.breakdown
        segments = calculated_slip.breakdown["salary_segments"]
        assert len(segments) == 2

        assert segments[0]["start_date"] == "2026-06-01"
        assert segments[0]["end_date"] == "2026-06-15"
        assert segments[0]["salary_base"] == 10000000.0

        assert segments[1]["start_date"] == "2026-06-16"
        assert segments[1]["end_date"] == "2026-06-30"
        assert segments[1]["salary_base"] == 12000000.0

        expected_total = Decimal(str(segments[0]["earned"])) + Decimal(str(segments[1]["earned"]))
        assert calculated_slip.base_salary == expected_total

    def test_create_partial_salary_slip_success(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_pr4_test6")

        slip = create_partial_salary_slip(
            employee_id=str(employee.id),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 15),
            name="SALARY-NV99-PARTIAL",
            creator=admin,
        )

        assert slip.status == "draft"
        assert slip.salary_period == "2026-06"
        assert slip.breakdown["is_partial"] is True
        assert slip.breakdown["period_start"] == "2026-06-01"
        assert slip.breakdown["period_end"] == "2026-06-15"

    def test_create_partial_salary_slip_validation(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_pr4_test7")

        with pytest.raises(ValidationException):
            create_partial_salary_slip(
                employee_id=str(employee.id),
                period_start=date(2026, 6, 15),
                period_end=date(2026, 6, 15),
                name="SALARY-INVALID",
                creator=admin,
            )

        with pytest.raises(ValidationException):
            create_partial_salary_slip(
                employee_id=str(employee.id),
                period_start=date(2026, 6, 15),
                period_end=date(2026, 7, 5),
                name="SALARY-INVALID",
                creator=admin,
            )

    def test_payroll_calculate_salary_partial(self):
        employee = EmployeeFactory(
            employee_id="NV_PARTIAL", salary_base__create_contract=False, employment_status="active"
        )
        admin = UserFactory(username="admin_pr4_test8")

        EmploymentContractFactory(
            employee=employee,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            status="active",
            salary_base=Decimal("26000000.00"),
        )

        for d in range(1, 6):
            AttendanceFactory(employee=employee, date=date(2026, 6, d), status="working", work_hours=Decimal("8.00"))

        slip = create_partial_salary_slip(
            employee_id=str(employee.id),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 5),
            name="SALARY-NV099-PARTIAL",
            creator=admin,
        )

        calculated_slip = payroll_calculate_salary(salary_slip_id=str(slip.id), creator=admin)

        assert calculated_slip.status == "calculated"
        assert calculated_slip.breakdown["is_partial"] is True
        assert calculated_slip.base_salary == Decimal("5000000.00")

    def test_payroll_submit(self):
        employee = EmployeeFactory()
        admin = UserFactory(username="admin_pr4_test9")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="calculated")

        submitted_slip = payroll_submit_for_review(salary_slip_id=str(slip.id), user=admin)
        assert submitted_slip.status == "pending_finance_review"

        # Nếu slip ở trạng thái draft, không cho submit
        submitted_slip.status = "draft"
        submitted_slip.save()
        with pytest.raises(ValidationException):
            payroll_submit_for_review(salary_slip_id=str(slip.id), user=admin)

    def test_payroll_bulk_calculate_drafts(self):
        # Arrange
        employee1 = EmployeeFactory(salary_base=Decimal("13000000.00"))
        employee2 = EmployeeFactory(salary_base=Decimal("13000000.00"))
        admin = UserFactory(username="admin_pr_bulk_1")
        slip1 = SalarySlipFactory(employee=employee1, salary_period="2026-06", status="draft")
        slip2 = SalarySlipFactory(employee=employee2, salary_period="2026-06", status="draft")

        EmploymentContractFactory(
            employee=employee1, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30), status="active"
        )
        EmploymentContractFactory(
            employee=employee2, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30), status="active"
        )

        # Act
        result = payroll_bulk_calculate(salary_period="2026-06", creator=admin)

        # Assert
        assert result["count"] == 2
        slip1.refresh_from_db()
        slip2.refresh_from_db()
        assert slip1.status == "calculated"
        assert slip2.status == "calculated"

    def test_payroll_bulk_calculate_calculated_slips(self):
        # Arrange
        employee = EmployeeFactory(salary_base=Decimal("12000000.00"))
        admin = UserFactory(username="admin_pr_bulk_recalc")
        slip = SalarySlipFactory(employee=employee, salary_period="2026-06", status="calculated")
        EmploymentContractFactory(
            employee=employee, start_date=date(2026, 6, 1), end_date=date(2026, 6, 30), status="active"
        )

        # Act
        result = payroll_bulk_calculate(salary_period="2026-06", creator=admin)

        # Assert
        assert result["count"] == 1
        slip.refresh_from_db()
        assert slip.status == "calculated"

    def test_payroll_bulk_submit_for_review(self):
        # Arrange
        employee1 = EmployeeFactory()
        employee2 = EmployeeFactory()
        admin = UserFactory(username="admin_pr_bulk_2")
        slip1 = SalarySlipFactory(employee=employee1, salary_period="2026-05", status="calculated")
        slip2 = SalarySlipFactory(employee=employee2, salary_period="2026-05", status="calculated")

        # Act
        result = payroll_bulk_submit_for_review(salary_period="2026-05", user=admin)

        # Assert
        assert result["count"] == 2
        slip1.refresh_from_db()
        slip2.refresh_from_db()
        assert slip1.status == "pending_finance_review"
        assert slip2.status == "pending_finance_review"

        # Check validation exception when none is in calculated state
        with pytest.raises(ValidationException, match="Không có phiếu lương nào ở trạng thái 'calculated'"):
            payroll_bulk_submit_for_review(salary_period="2026-05", user=admin)

    def test_attendance_batch_record_blocked_when_period_paid(self):
        employee = EmployeeFactory(employee_id="EMP_CONSTRAINT_1", employment_status="active")
        admin = UserFactory(username="admin_constraint_1")
        SalarySlipFactory(employee=employee, salary_period="2026-05", status="paid")

        records = [{"employee_id": str(employee.id), "status": "working", "work_hours": Decimal("8.00")}]
        with pytest.raises(ValidationException) as exc_info:
            attendance_batch_record(date=date(2026, 5, 15), records=records, creator=admin)

        assert "Kỳ lương 2026-05 đã được thanh toán 100%" in str(exc_info.value)

    def test_leave_request_approve_blocked_when_period_paid(self):
        employee = EmployeeFactory(employee_id="EMP_CONSTRAINT_2", employment_status="active")
        admin = UserFactory(username="admin_constraint_2")
        SalarySlipFactory(employee=employee, salary_period="2026-05", status="paid")

        leave_data = {
            "leave_type": "paid",
            "start_date": date(2026, 5, 10),
            "end_date": date(2026, 5, 12),
            "days": Decimal("3.0"),
            "reason": "Nghỉ phép",
        }
        request = leave_request_create(employee_id=employee.id, data=leave_data)

        with pytest.raises(ValidationException) as exc_info:
            leave_request_approve(leave_request_id=request.id, approved_by_user_id=admin.id)

        assert "Kỳ lương 2026-05 đã được thanh toán 100%" in str(exc_info.value)

    def test_employee_deletion_blocked_by_protected_records(self):
        from django.db.models.deletion import ProtectedError

        employee = EmployeeFactory(employee_id="EMP_CONSTRAINT_3", employment_status="active")
        AttendanceFactory(employee=employee, date=date(2026, 5, 15), status="working")

        with pytest.raises(ProtectedError):
            employee.delete()

    def test_calculate_blocked_on_paid_slip(self):
        employee = EmployeeFactory(
            employee_id="EMPP_PAID_BLOCKED", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        slip = SalarySlipFactory(employee=employee, salary_period="2026-05", status="paid")
        admin = UserFactory(username="admin_paid_blocked")

        with pytest.raises(ValidationException) as exc_info:
            payroll_calculate_salary(salary_slip_id=str(slip.id), creator=admin)
        assert "Không thể tính lại phiếu lương đã thanh toán" in str(exc_info.value)

    def test_contract_terminate_creates_slip_in_pending_finance_review_status(self):
        employee = EmployeeFactory(
            employee_id="EMP_NEW_1", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-NEW-1", status="active", salary_base=Decimal("10000000.00")
        )
        admin = UserFactory(username="admin_new_1")
        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 15),
            reason="Thôi việc",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
        )

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "pending_finance_review"

    def test_contract_terminate_does_not_create_cash_flow_transaction(self):
        employee = EmployeeFactory(
            employee_id="EMP_NEW_2", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-NEW-2", status="active", salary_base=Decimal("10000000.00")
        )
        admin = UserFactory(username="admin_new_2")

        initial_count = CashFlowTransaction.objects.count()
        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 15),
            reason="Thôi việc",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
        )
        assert CashFlowTransaction.objects.count() == initial_count

    def test_contract_terminate_route_through_finance_can_be_paid(self):
        employee = EmployeeFactory(
            employee_id="NV_NEW_3", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-NEW-3", status="active", salary_base=Decimal("10000000.00")
        )
        admin = UserFactory(username="admin_new_3")

        AttendanceFactory(employee=employee, date=date(2026, 5, 5), status="working", work_hours=Decimal("8.00"))

        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 15),
            reason="Thôi việc",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
        )
        from apps.finance.services import payroll_approve_slip, payroll_pay_slip

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")

        # Finance approves the slip
        payroll_approve_slip(user=admin, salary_slip_id=str(slip.id))
        slip.refresh_from_db()
        assert slip.status == "approved"

        # Finance pays the slip
        payroll_pay_slip(user=admin, salary_slip_id=str(slip.id), payment_method="bank_transfer")
        slip.refresh_from_db()
        assert slip.status == "paid"

        assert CashFlowTransaction.objects.filter(name__contains=employee.employee_id).exists()

    def test_contract_terminate_with_prorated_calculation_mid_month(self):
        employee = EmployeeFactory(
            employee_id="NV_NEW_4", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-NEW-4", status="active", salary_base=Decimal("26000000.00")
        )
        admin = UserFactory(username="admin_new_4")
        for day in range(1, 16):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 15),
            reason="Thôi việc",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
        )

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.breakdown.get("is_partial") is True
        assert slip.breakdown.get("period_end") == "2026-05-15"
        assert slip.base_salary == Decimal("15000000.00")

    def test_contract_terminate_full_month_calculation_end_of_month(self):
        employee = EmployeeFactory(
            employee_id="NV_NEW_5", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-NEW-5", status="active", salary_base=Decimal("26000000.00")
        )
        admin = UserFactory(username="admin_new_5")
        for day in range(1, 27):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        contract_terminate(
            contract_id=contract.id,
            termination_date=date(2026, 5, 31),
            reason="Thôi việc cuối tháng",
            terminator=admin,
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
        )

        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.breakdown.get("is_partial") is True
        assert slip.breakdown.get("period_end") == "2026-05-31"
        assert slip.base_salary == Decimal("26000000.00")

    def test_contract_terminate_rollback_when_terminated_calculate_fails(self):
        employee = EmployeeFactory(
            employee_id="NV_NEW_6", salary_base__create_contract=False, employment_status="active"
        )
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-NEW-6", status="active", salary_base=Decimal("10000000.00")
        )
        admin = UserFactory(username="admin_new_6")

        initial_contract_status = contract.status
        initial_emp_status = employee.employment_status

        with patch(
            "apps.hrm.services.payroll_calculate_terminated_salary",
            side_effect=ValidationException("Calculated failed"),
        ):
            with pytest.raises(ValidationException, match="Calculated failed"):
                contract_terminate(
                    contract_id=contract.id,
                    termination_date=date(2026, 5, 15),
                    reason="Thôi việc",
                    terminator=admin,
                    is_lawful=True,
                )

        contract.refresh_from_db()
        employee.refresh_from_db()
        assert contract.status == initial_contract_status
        assert employee.employment_status == initial_emp_status

    def test_contract_terminate_rollback_when_submit_for_review_fails(self):
        employee = EmployeeFactory(
            employee_id="EMP_NEW_7", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-NEW-7", status="active")
        admin = UserFactory(username="admin_new_7")

        initial_contract_status = contract.status
        initial_emp_status = employee.employment_status

        with patch("apps.hrm.services.payroll_submit_for_review", side_effect=ValidationException("Submit failed")):
            with pytest.raises(ValidationException, match="Submit failed"):
                contract_terminate(
                    contract_id=contract.id,
                    termination_date=date(2026, 5, 15),
                    reason="Thôi việc",
                    terminator=admin,
                    is_lawful=True,
                )

        contract.refresh_from_db()
        employee.refresh_from_db()
        assert contract.status == initial_contract_status
        assert employee.employment_status == initial_emp_status

    def test_is_salary_period_fully_paid_returns_true_for_pending_finance_review(self):
        from apps.hrm.selectors import is_salary_period_fully_paid

        employee = EmployeeFactory(employee_id="EMP_NEW_8")
        SalarySlipFactory(employee=employee, salary_period="2026-05", status="pending_finance_review")
        assert is_salary_period_fully_paid("2026-05") is True

    def test_terminated_calculate_calculates_4_regular_components_via_calculate(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_1", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        EmploymentContractFactory(employee=employee, contract_no="HDLD-CALC-1", status="active")
        admin = UserFactory(username="admin_calc_1")
        for day in range(1, 11):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        slip = SalarySlip.objects.create(
            employee=employee,
            salary_period="2026-05",
            name="TEST-SLIP-CALC-1",
            status="draft",
            breakdown={"is_partial": True, "period_start": "2026-05-01", "period_end": "2026-05-15"},
        )
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=date(2026, 5, 15),
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
            creator=admin,
        )
        slip.refresh_from_db()
        assert slip.base_salary == Decimal("3846153.85")
        assert slip.status == "calculated"

    def test_terminated_calculate_adds_unused_leave_compensation(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_2", salary_base=Decimal("26000000.00"), employment_status="active"
        )
        EmploymentContractFactory(employee=employee, contract_no="HDLD-CALC-2", status="active")
        admin = UserFactory(username="admin_calc_2")

        slip = SalarySlip.objects.create(
            employee=employee,
            salary_period="2026-05",
            name="TEST-SLIP-CALC-2",
            status="draft",
            breakdown={"is_partial": True, "period_start": "2026-05-01", "period_end": "2026-05-15"},
        )
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=date(2026, 5, 15),
            is_lawful=True,
            unused_leave_days=Decimal("3.0"),
            standard_working_days=26,
            creator=admin,
        )
        slip.refresh_from_db()
        assert slip.gross_pay == Decimal("3000000.00")

    def test_terminated_calculate_adds_social_insurance_when_working_over_14_days(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_3", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        EmploymentContractFactory(employee=employee, contract_no="HDLD-CALC-3", status="active")
        admin = UserFactory(username="admin_calc_3")
        for day in range(1, 15):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        slip = SalarySlip.objects.create(
            employee=employee,
            salary_period="2026-05",
            name="TEST-SLIP-CALC-3",
            status="draft",
            breakdown={"is_partial": True, "period_start": "2026-05-01", "period_end": "2026-05-15"},
        )
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=date(2026, 5, 15),
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
            creator=admin,
        )
        slip.refresh_from_db()
        assert slip.deductions == Decimal("1050000.00")

    def test_terminated_calculate_skips_social_insurance_when_working_under_14_days(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_4", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        EmploymentContractFactory(employee=employee, contract_no="HDLD-CALC-4", status="active")
        admin = UserFactory(username="admin_calc_4")
        for day in range(1, 14):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        slip = SalarySlip.objects.create(
            employee=employee,
            salary_period="2026-05",
            name="TEST-SLIP-CALC-4",
            status="draft",
            breakdown={"is_partial": True, "period_start": "2026-05-01", "period_end": "2026-05-15"},
        )
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=date(2026, 5, 15),
            is_lawful=True,
            unused_leave_days=Decimal("0.0"),
            standard_working_days=26,
            creator=admin,
        )
        slip.refresh_from_db()
        assert slip.deductions == Decimal("0.00")

    def test_terminated_calculate_adds_resignation_fine_when_not_lawful(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_5", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        EmploymentContractFactory(employee=employee, contract_no="HDLD-CALC-5", status="active")
        admin = UserFactory(username="admin_calc_5")

        slip = SalarySlip.objects.create(
            employee=employee,
            salary_period="2026-05",
            name="TEST-SLIP-CALC-5",
            status="draft",
            breakdown={"is_partial": True, "period_start": "2026-05-01", "period_end": "2026-05-15"},
        )
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=date(2026, 5, 15),
            is_lawful=False,
            unused_leave_days=Decimal("0.0"),
            unnotified_days=30,
            standard_working_days=26,
            creator=admin,
        )
        slip.refresh_from_db()
        assert slip.deductions == Decimal("16538461.54")

    def test_terminated_calculate_raises_when_breakdown_is_partial_missing(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_6", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        admin = UserFactory(username="admin_calc_6")

        slip = SalarySlip.objects.create(
            employee=employee, salary_period="2026-05", name="TEST-SLIP-CALC-6", status="draft", breakdown={}
        )
        with pytest.raises(ValidationException, match="Phiếu lương quyết toán phải có breakdown.is_partial=True"):
            payroll_calculate_terminated_salary(
                salary_slip_id=str(slip.id), termination_date=date(2026, 5, 15), is_lawful=True, creator=admin
            )

    def test_terminated_calculate_raises_when_slip_already_paid(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_7", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        admin = UserFactory(username="admin_calc_7")

        slip = SalarySlip.objects.create(
            employee=employee,
            salary_period="2026-05",
            name="TEST-SLIP-CALC-7",
            status="paid",
            breakdown={"is_partial": True, "period_start": "2026-05-01", "period_end": "2026-05-15"},
        )
        with pytest.raises(ValidationException, match="Không thể tính lại phiếu lương đã thanh toán"):
            payroll_calculate_terminated_salary(
                salary_slip_id=str(slip.id), termination_date=date(2026, 5, 15), is_lawful=True, creator=admin
            )

    def test_calc_termination_compensation_lawful_full_month(self):
        comp = _calc_termination_compensation(
            salary_base=Decimal("10000000.00"),
            working_days=Decimal("26.00"),
            paid_leave_days=Decimal("0.00"),
            is_lawful=True,
            unused_leave_days=Decimal("0.00"),
            unnotified_days=0,
            standard_working_days=26,
        )
        assert comp["unused_leave_compensation"] == Decimal("0.00")
        assert comp["social_insurance_deduction"] == Decimal("1050000.00")
        assert comp["resignation_fine"] == Decimal("0.00")

    def test_calc_termination_compensation_lawful_with_unused_leave(self):
        comp = _calc_termination_compensation(
            salary_base=Decimal("10400000.00"),
            working_days=Decimal("10.00"),
            paid_leave_days=Decimal("0.00"),
            is_lawful=True,
            unused_leave_days=Decimal("3.00"),
            unnotified_days=0,
            standard_working_days=26,
        )
        assert comp["unused_leave_compensation"] == Decimal("1200000.00")
        assert comp["social_insurance_deduction"] == Decimal("0.00")
        assert comp["resignation_fine"] == Decimal("0.00")

    def test_calc_termination_compensation_unlawful_with_fine(self):
        comp = _calc_termination_compensation(
            salary_base=Decimal("10400000.00"),
            working_days=Decimal("15.00"),
            paid_leave_days=Decimal("0.00"),
            is_lawful=False,
            unused_leave_days=Decimal("0.00"),
            unnotified_days=30,
            standard_working_days=26,
        )
        assert comp["resignation_fine"] == Decimal("17200000.00")
        assert comp["social_insurance_deduction"] == Decimal("1092000.00")

    def test_calc_termination_compensation_under_14_days_no_bhxh(self):
        comp = _calc_termination_compensation(
            salary_base=Decimal("10000000.00"),
            working_days=Decimal("13.00"),
            paid_leave_days=Decimal("0.00"),
            is_lawful=True,
            unused_leave_days=Decimal("0.00"),
            unnotified_days=0,
            standard_working_days=26,
        )
        assert comp["social_insurance_deduction"] == Decimal("0.00")

    def test_payroll_calculate_terminated_salary_retry_preserves_segments(self):
        employee = EmployeeFactory(
            employee_id="EMP_CALC_RETRY", salary_base=Decimal("10000000.00"), employment_status="active"
        )
        contract = EmploymentContractFactory(employee=employee, contract_no="HDLD-CALC-RETRY", status="active")
        admin = UserFactory(username="admin_calc_retry")
        for day in range(1, 11):
            AttendanceFactory(employee=employee, date=date(2026, 5, day), status="working", work_hours=Decimal("8.00"))

        slip = SalarySlip.objects.create(
            employee=employee,
            salary_period="2026-05",
            name="TEST-SLIP-CALC-RETRY",
            status="draft",
            breakdown={"is_partial": True, "period_start": "2026-05-01", "period_end": "2026-05-15"},
        )
        # Lần 1: Tính lương quyết toán
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=date(2026, 5, 15),
            is_lawful=True,
            unused_leave_days=Decimal("2.0"),
            standard_working_days=26,
            creator=admin,
        )
        slip.refresh_from_db()
        assert "salary_segments" in slip.breakdown
        assert len(slip.breakdown["salary_segments"]) > 0

        # Terminate HĐLĐ của nhân viên
        contract.status = "terminated"
        contract.save()

        # Lần 2 (retry): Tính lại lương quyết toán khi contract không còn active
        payroll_calculate_terminated_salary(
            salary_slip_id=str(slip.id),
            termination_date=date(2026, 5, 15),
            is_lawful=True,
            unused_leave_days=Decimal("2.0"),
            standard_working_days=26,
            creator=admin,
        )
        slip.refresh_from_db()
        assert "salary_segments" in slip.breakdown
        assert len(slip.breakdown["salary_segments"]) > 0


@pytest.mark.django_db
class TestHrmCompensatoryHolidayRules:

    def test_compensatory_holiday_overlap_sunday(self):
        from apps.hrm.services import get_holiday_dates_for_period

        # May 3rd, 2026 is a Sunday
        PublicHoliday.objects.create(name="Lễ Trùng Chủ Nhật", start_date=date(2026, 5, 3), days=1)

        official, compensatory = get_holiday_dates_for_period(2026, 5)

        assert date(2026, 5, 3) in official
        assert date(2026, 5, 4) in compensatory
        assert len(official) == 1
        assert len(compensatory) == 1

    def test_holiday_on_saturday_no_compensation(self):
        from apps.hrm.services import get_holiday_dates_for_period

        # May 2nd, 2026 is a Saturday
        PublicHoliday.objects.create(name="Lễ Thứ Bảy", start_date=date(2026, 5, 2), days=1)

        official, compensatory = get_holiday_dates_for_period(2026, 5)

        assert date(2026, 5, 2) in official
        assert len(compensatory) == 0

    def test_compensatory_holiday_multi_day_block_ends_tuesday(self):
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
        # Arrange
        employee = EmployeeFactory(
            employee_id="EMP8805",
            salary_base=Decimal("10400000.00"),  # 400.000 / day, 50.000 / hour
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
        assert calculated_slip.base_salary == Decimal("800000.00")
        assert calculated_slip.overtime_amount == Decimal("400000.00")

        incomes = calculated_slip.breakdown["incomes"]
        comp_ot_entry = next((inc for inc in incomes if "ngày nghỉ bù" in inc["name"]), None)
        assert comp_ot_entry is not None
        assert comp_ot_entry["amount"] == 400000.0

    def test_contract_terminate_with_compensatory_holidays(self):
        # Arrange
        employee = EmployeeFactory(
            employee_id="NV8806",
            salary_base__create_contract=False,
            employment_status="active",
        )
        contract = EmploymentContractFactory(
            employee=employee, contract_no="HDLD-8806", status="active", salary_base=Decimal("10400000.00")
        )
        admin = UserFactory(username="admin_comp_term")

        # May 3rd, 2026 is Sunday, May 4th is compensatory holiday
        PublicHoliday.objects.create(name="Lễ Chủ Nhật", start_date=date(2026, 5, 3), days=1)

        AttendanceFactory(
            employee=employee,
            date=date(2026, 5, 4),
            status="working",
            work_hours=Decimal("8.00"),
            overtime_hours=Decimal("4.00"),
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
        slip = SalarySlip.objects.get(employee=employee, salary_period="2026-05")
        assert slip.status == "pending_finance_review"
        assert slip.base_salary == Decimal("1200000.00")
        assert slip.overtime_amount == Decimal("400000.00")

        incomes = slip.breakdown["incomes"]
        comp_ot_entry = next((inc for inc in incomes if "ngày nghỉ bù" in inc["name"]), None)
        assert comp_ot_entry is not None
        assert comp_ot_entry["amount"] == 400000.0
        assert slip.breakdown["standard_working_days"] == 26
